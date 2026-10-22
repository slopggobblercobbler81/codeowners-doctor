"""Linter and diagnostics engine for CODEOWNERS."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Set

from codeowners_doctor.matcher import CodeOwnersMatcher, compile_pattern_to_regex
from codeowners_doctor.models import (
    CodeOwnersLine,
    Diagnostic,
    DiagnosticSeverity,
    LineType,
    OwnerKind,
)
from codeowners_doctor.parser import CodeOwnersParser


IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "dist",
    "build",
}


def get_repository_files(repo_root: Path) -> List[str]:
    """Retrieves all tracked or existing files in repository, normalized to POSIX relative paths."""
    # Try git ls-files first if git repository
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            files = [
                CodeOwnersMatcher.normalize_path(line)
                for line in proc.stdout.splitlines()
                if line.strip()
            ]
            if files:
                return files
    except Exception:
        pass

    # Fallback to filesystem walk
    files = []
    for root, dirs, filenames in os.walk(repo_root):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and d != ".git" and not d.startswith(".git/")]
        rel_root = Path(root).relative_to(repo_root)

        for fname in filenames:
            rel_path = (rel_root / fname).as_posix()
            if rel_path.startswith("./"):
                rel_path = rel_path[2:]
            files.append(rel_path)

    return sorted(files)


class CodeOwnersLinter:
    """Performs validation, syntax checking, and static analysis on CODEOWNERS."""

    def __init__(
        self,
        lines: List[CodeOwnersLine],
        repo_root: Optional[Path] = None,
        codeowners_path: Optional[Path] = None,
    ):
        self.lines = lines
        self.repo_root = repo_root
        self.codeowners_path = codeowners_path
        self.diagnostics: List[Diagnostic] = []

    def run_all(self, check_unowned: bool = False) -> List[Diagnostic]:
        """Runs all lint checks and returns a list of diagnostics."""
        self.diagnostics.clear()

        self.check_syntax_and_owners()
        self.check_duplicate_owners()
        self.check_redundant_wildcards()
        self.check_shadowed_rules()

        if self.repo_root and self.repo_root.is_dir():
            repo_files = get_repository_files(self.repo_root)
            self.check_orphan_patterns(repo_files)
            if check_unowned:
                self.check_unowned_files(repo_files)

        return self.diagnostics

    def check_syntax_and_owners(self) -> None:
        """Checks for pattern compilation errors, empty rules, and invalid owner formats."""
        for line in self.lines:
            if line.line_type != LineType.RULE:
                continue

            if not line.pattern:
                self.diagnostics.append(
                    Diagnostic(
                        code="E001",
                        message="Rule line has no pattern specified.",
                        severity=DiagnosticSeverity.ERROR,
                        line_number=line.line_number,
                        rule_line=line.raw,
                    )
                )
                continue

            # Verify pattern compiles to regex
            try:
                compile_pattern_to_regex(line.pattern)
            except Exception as e:
                self.diagnostics.append(
                    Diagnostic(
                        code="E001",
                        message=f"Invalid pattern syntax '{line.pattern}': {e}",
                        severity=DiagnosticSeverity.ERROR,
                        line_number=line.line_number,
                        rule_line=line.raw,
                    )
                )

            # Check if owners are missing
            if not line.owners:
                self.diagnostics.append(
                    Diagnostic(
                        code="E002",
                        message=f"Pattern '{line.pattern}' has no code owners defined.",
                        severity=DiagnosticSeverity.ERROR,
                        line_number=line.line_number,
                        suggestion="Specify at least one owner (e.g., @username, @org/team, or user@example.com).",
                        rule_line=line.raw,
                    )
                )
                continue

            # Validate each owner token
            for parsed_owner in line.parsed_owners:
                if parsed_owner.kind == OwnerKind.INVALID:
                    self.diagnostics.append(
                        Diagnostic(
                            code="E003",
                            message=f"Invalid owner format '{parsed_owner.raw}'.",
                            severity=DiagnosticSeverity.ERROR,
                            line_number=line.line_number,
                            suggestion="Owners must be a GitHub user (@user), team (@org/team), or valid email address.",
                            rule_line=line.raw,
                        )
                    )

    def check_duplicate_owners(self) -> None:
        """Flags lines where the same owner is declared multiple times."""
        for line in self.lines:
            if line.line_type != LineType.RULE:
                continue

            seen: Set[str] = set()
            duplicates: Set[str] = set()
            for o in line.owners:
                norm_o = o.lower()
                if norm_o in seen:
                    duplicates.add(o)
                seen.add(norm_o)

            if duplicates:
                dup_str = ", ".join(sorted(duplicates))
                self.diagnostics.append(
                    Diagnostic(
                        code="W001",
                        message=f"Duplicate owner(s) on line: {dup_str}",
                        severity=DiagnosticSeverity.WARNING,
                        line_number=line.line_number,
                        suggestion="Remove redundant owner declarations on this line.",
                        rule_line=line.raw,
                    )
                )

    def check_redundant_wildcards(self) -> None:
        """Checks for strange or redundant wildcards like './pattern' or '**/**'."""
        for line in self.lines:
            if line.line_type != LineType.RULE or not line.pattern:
                continue

            if line.pattern.startswith("./"):
                self.diagnostics.append(
                    Diagnostic(
                        code="W005",
                        message=f"Pattern '{line.pattern}' has redundant leading './'.",
                        severity=DiagnosticSeverity.WARNING,
                        line_number=line.line_number,
                        suggestion=f"Change to '{line.pattern[2:]}' or '/{line.pattern[2:]}'.",
                        rule_line=line.raw,
                    )
                )

            if "**/**" in line.pattern:
                self.diagnostics.append(
                    Diagnostic(
                        code="W005",
                        message=f"Pattern '{line.pattern}' contains redundant '**/**'.",
                        severity=DiagnosticSeverity.WARNING,
                        line_number=line.line_number,
                        suggestion="Replace '**/**' with '**'.",
                        rule_line=line.raw,
                    )
                )

    def check_shadowed_rules(self) -> None:
        """Flags earlier rules that are completely shadowed or overwritten by later rules."""
        rules = [l for l in self.lines if l.line_type == LineType.RULE and l.pattern]

        for i, rule1 in enumerate(rules):
            p1 = rule1.pattern.strip()
            # Compare with subsequent rules
            for rule2 in rules[i + 1 :]:
                p2 = rule2.pattern.strip()

                # Identical pattern later completely shadows earlier pattern
                if p1 == p2:
                    self.diagnostics.append(
                        Diagnostic(
                            code="W002",
                            message=(
                                f"Rule '{p1}' on line {rule1.line_number} is completely shadowed by "
                                f"identical pattern on line {rule2.line_number}."
                            ),
                            severity=DiagnosticSeverity.WARNING,
                            line_number=rule1.line_number,
                            suggestion="Remove or reorder the earlier duplicate pattern.",
                            rule_line=rule1.raw,
                        )
                    )
                    break

                # Global wildcard '*' later shadows earlier rules unless under different sections
                if p2 == "*" and rule1.section == rule2.section:
                    self.diagnostics.append(
                        Diagnostic(
                            code="W002",
                            message=(
                                f"Rule '{p1}' on line {rule1.line_number} is shadowed by "
                                f"catch-all '*' on line {rule2.line_number}."
                            ),
                            severity=DiagnosticSeverity.WARNING,
                            line_number=rule1.line_number,
                            suggestion="Place catch-all '*' rules at the very top of the file.",
                            rule_line=rule1.raw,
                        )
                    )
                    break

    def check_orphan_patterns(self, repo_files: List[str]) -> None:
        """Flags rules whose patterns match zero files in the repository."""
        if not repo_files:
            return

        for line in self.lines:
            if line.line_type != LineType.RULE or not line.pattern:
                continue

            try:
                regex = compile_pattern_to_regex(line.pattern)
            except Exception:
                continue

            matched_any = any(regex.match(f) for f in repo_files)
            if not matched_any:
                self.diagnostics.append(
                    Diagnostic(
                        code="W003",
                        message=f"Orphan pattern '{line.pattern}' matches 0 files in repository.",
                        severity=DiagnosticSeverity.WARNING,
                        line_number=line.line_number,
                        suggestion="Update pattern to match existing files or delete if no longer needed.",
                        rule_line=line.raw,
                    )
                )

    def check_unowned_files(self, repo_files: List[str]) -> None:
        """Flags repository files that have no matching CODEOWNERS rule."""
        matcher = CodeOwnersMatcher(self.lines)
        unowned_count = 0
        examples: List[str] = []

        for f in repo_files:
            res = matcher.match_file(f)
            if not res.matched:
                unowned_count += 1
                if len(examples) < 5:
                    examples.append(f)

        if unowned_count > 0:
            sample_str = ", ".join(examples)
            if unowned_count > 5:
                sample_str += f", and {unowned_count - 5} more..."
            self.diagnostics.append(
                Diagnostic(
                    code="W004",
                    message=f"Found {unowned_count} unowned file(s) without CODEOWNERS coverage: {sample_str}",
                    severity=DiagnosticSeverity.WARNING,
                    suggestion="Add a catch-all '*' rule or specific rules covering these files.",
                )
            )
