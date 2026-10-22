"""Linter and diagnostics engine for CODEOWNERS files."""

from __future__ import annotations
import enum
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .parser import CodeownersRule, ParsedCodeowners, is_valid_owner, parse_codeowners
from .matcher import CodeownersMatcher, pattern_to_regex, normalize_repo_path


class IssueSeverity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class LintIssue:
    """Represents a diagnostic issue discovered in a CODEOWNERS file."""
    code: str
    message: str
    severity: IssueSeverity
    line_number: Optional[int] = None
    rule: Optional[CodeownersRule] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "line_number": self.line_number,
            "pattern": self.rule.pattern if self.rule else None,
            "suggestion": self.suggestion,
        }


@dataclass
class LintReport:
    """Aggregated lint results and metrics."""
    issues: List[LintIssue] = field(default_factory=list)
    total_rules: int = 0
    total_lines: int = 0
    repo_scanned: Optional[str] = None

    @property
    def errors(self) -> List[LintIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> List[LintIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    @property
    def infos(self) -> List[LintIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.INFO]

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> dict:
        return {
            "is_clean": self.is_clean,
            "total_rules": self.total_rules,
            "total_lines": self.total_lines,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.infos),
            "issues": [i.to_dict() for i in self.issues],
        }

    def to_sarif(self) -> dict:
        """Convert lint report to SARIF format for GitHub Code Scanning."""
        rules_map = {}
        results = []

        for issue in self.issues:
            rule_id = issue.code
            if rule_id not in rules_map:
                rules_map[rule_id] = {
                    "id": rule_id,
                    "name": rule_id.replace("_", " ").title(),
                    "shortDescription": {"text": issue.message},
                    "defaultConfiguration": {
                        "level": "error" if issue.severity == IssueSeverity.ERROR else "warning"
                    },
                }

            level = "error" if issue.severity == IssueSeverity.ERROR else (
                "warning" if issue.severity == IssueSeverity.WARNING else "note"
            )

            result = {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": issue.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "CODEOWNERS"},
                            "region": {
                                "startLine": issue.line_number or 1,
                                "startColumn": 1,
                            },
                        }
                    }
                ],
            }
            results.append(result)

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "codeowners-doctor",
                            "version": "0.1.0",
                            "rules": list(rules_map.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }


CRITICAL_SECURITY_PATHS = [
    ".github/workflows",
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "Dockerfile",
    "docker-compose.yml",
    "security",
    "auth",
]


class CodeownersLinter:
    """Comprehensive linter verifying syntax, logic, coverage, and dead rules."""

    def __init__(
        self,
        repo_dir: Optional[str | Path] = None,
        files_list: Optional[Sequence[str]] = None,
        check_dead_rules: bool = True,
        check_critical_paths: bool = True,
    ) -> None:
        self.repo_dir = Path(repo_dir) if repo_dir else None
        self.files_list = list(files_list) if files_list is not None else None
        self.check_dead_rules = check_dead_rules
        self.check_critical_paths = check_critical_paths

    def _discover_repo_files(self) -> List[str]:
        """Discover existing tracked or visible files in repository."""
        if self.files_list is not None:
            return self.files_list

        if not self.repo_dir or not self.repo_dir.is_dir():
            return []

        discovered: List[str] = []
        ignored_dirs = {".git", ".pytest_cache", ".mypy_cache", "__pycache__", "node_modules", "venv", ".venv"}

        for root, dirs, files in os.walk(self.repo_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            rel_dir = os.path.relpath(root, self.repo_dir)

            for f in files:
                rel_path = f if rel_dir == "." else os.path.join(rel_dir, f)
                discovered.append(normalize_repo_path(rel_path))

        return discovered

    def lint(self, content_or_parsed: str | ParsedCodeowners) -> LintReport:
        """Run all lint rules against CODEOWNERS content."""
        if isinstance(content_or_parsed, str):
            parsed = parse_codeowners(content_or_parsed)
            raw_lines = content_or_parsed.splitlines()
        else:
            parsed = content_or_parsed
            raw_lines = parsed.raw_lines

        report = LintReport(
            total_rules=len(parsed.rules),
            total_lines=len(raw_lines),
            repo_scanned=str(self.repo_dir) if self.repo_dir else None,
        )

        # 1. Line-level hygiene checks (trailing whitespace, backslashes)
        for idx, line in enumerate(raw_lines, start=1):
            if line.endswith(" ") or line.endswith("\t"):
                report.issues.append(
                    LintIssue(
                        code="TRAILING_WHITESPACE",
                        message=f"Line {idx} contains trailing whitespace.",
                        severity=IssueSeverity.WARNING,
                        line_number=idx,
                        suggestion="Remove trailing whitespace.",
                    )
                )

        # 2. Rule-level syntax & owner checks
        seen_exact_rules: Dict[Tuple[str, Tuple[str, ...]], int] = {}
        patterns_to_rules: Dict[str, List[CodeownersRule]] = {}

        for rule in parsed.rules:
            patterns_to_rules.setdefault(rule.pattern, []).append(rule)

            # Check backslashes in pattern
            if "\\" in rule.pattern and not any(f"\\{c}" in rule.pattern for c in (" ", "#", "[", "]", "*")):
                fixed_pattern = rule.pattern.replace("\\", "/")
                report.issues.append(
                    LintIssue(
                        code="BACKSLASH_IN_PATTERN",
                        message=f"Line {rule.line_number}: Pattern '{rule.pattern}' contains unescaped backslashes. CODEOWNERS uses forward slashes '/'.",
                        severity=IssueSeverity.WARNING,
                        line_number=rule.line_number,
                        rule=rule,
                        suggestion=f"Replace '\\' with '/': '{fixed_pattern}'",
                    )
                )

            # Check empty owners (explicit unowning vs possible mistake)
            if not rule.owners:
                report.issues.append(
                    LintIssue(
                        code="MISSING_OWNERS",
                        message=f"Line {rule.line_number}: Pattern '{rule.pattern}' specifies no owners (clears ownership).",
                        severity=IssueSeverity.INFO,
                        line_number=rule.line_number,
                        rule=rule,
                        suggestion="Assign at least one @user or @team if this wasn't intentional.",
                    )
                )

            # Check owner validity & duplicate owners on same rule
            seen_rule_owners: Set[str] = set()
            for owner in rule.owners:
                if not is_valid_owner(owner):
                    report.issues.append(
                        LintIssue(
                            code="OWNER_FORMAT_INVALID",
                            message=f"Line {rule.line_number}: Invalid owner format '{owner}'. Expected @username, @org/team, or user@domain.com.",
                            severity=IssueSeverity.ERROR,
                            line_number=rule.line_number,
                            rule=rule,
                            suggestion=f"Prefix username with '@' or format as valid email: '@{owner}'",
                        )
                    )

                if owner in seen_rule_owners:
                    report.issues.append(
                        LintIssue(
                            code="DUPLICATE_OWNER",
                            message=f"Line {rule.line_number}: Duplicate owner '{owner}' specified on same pattern.",
                            severity=IssueSeverity.WARNING,
                            line_number=rule.line_number,
                            rule=rule,
                            suggestion=f"Remove duplicate '{owner}'.",
                        )
                    )
                seen_rule_owners.add(owner)

            # Check duplicate exact rules
            rule_key = (rule.pattern, rule.owners)
            if rule_key in seen_exact_rules:
                prev_line = seen_exact_rules[rule_key]
                report.issues.append(
                    LintIssue(
                        code="DUPLICATE_RULE",
                        message=f"Line {rule.line_number}: Duplicate rule for '{rule.pattern}' identical to line {prev_line}.",
                        severity=IssueSeverity.WARNING,
                        line_number=rule.line_number,
                        rule=rule,
                        suggestion=f"Remove redundant duplicate rule on line {rule.line_number}.",
                    )
                )
            else:
                seen_exact_rules[rule_key] = rule.line_number

        # 3. Shadowed rules analysis
        # If the same pattern appears multiple times with DIFFERENT owners, earlier occurrences are shadowed
        for pattern, rule_group in patterns_to_rules.items():
            if len(rule_group) > 1:
                # All except the last rule are shadowed by the last rule
                last_rule = rule_group[-1]
                for shadowed in rule_group[:-1]:
                    if shadowed.owners != last_rule.owners:
                        report.issues.append(
                            LintIssue(
                                code="SHADOWED_RULE",
                                message=(
                                    f"Line {shadowed.line_number}: Rule for '{pattern}' is shadowed and completely "
                                    f"overridden by line {last_rule.line_number}."
                                ),
                                severity=IssueSeverity.WARNING,
                                line_number=shadowed.line_number,
                                rule=shadowed,
                                suggestion=f"Consolidate with line {last_rule.line_number} or reorder.",
                            )
                        )

        # 4. Dead rules detection (requires repository files)
        repo_files = self._discover_repo_files()
        if self.check_dead_rules and repo_files:
            for rule in parsed.rules:
                reg = pattern_to_regex(rule.pattern)
                has_match = any(reg.match(f) for f in repo_files)
                if not has_match:
                    report.issues.append(
                        LintIssue(
                            code="DEAD_RULE",
                            message=f"Line {rule.line_number}: Pattern '{rule.pattern}' matched 0 files in repository.",
                            severity=IssueSeverity.WARNING,
                            line_number=rule.line_number,
                            rule=rule,
                            suggestion="Remove dead rule or update pattern to match existing paths.",
                        )
                    )

        # 5. Critical paths check
        if self.check_critical_paths and repo_files:
            matcher = CodeownersMatcher(parsed)
            for crit_prefix in CRITICAL_SECURITY_PATHS:
                matching_files = [f for f in repo_files if f.startswith(crit_prefix)]
                for mf in matching_files:
                    if not matcher.is_owned(mf):
                        report.issues.append(
                            LintIssue(
                                code="UNOWNED_CRITICAL_PATH",
                                message=f"Critical path '{mf}' has no assigned owner in CODEOWNERS.",
                                severity=IssueSeverity.ERROR,
                                suggestion=f"Add a rule: '/{crit_prefix}* @security-team'",
                            )
                        )
                        break  # Report once per critical path prefix

        return report
