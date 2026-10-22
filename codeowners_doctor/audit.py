"""Repository ownership auditing and coverage metrics engine."""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .parser import ParsedCodeowners, parse_codeowners
from .matcher import CodeownersMatcher, normalize_repo_path


@dataclass
class OwnershipAuditReport:
    """Detailed metrics on repository ownership coverage and owner breakdown."""
    total_files: int
    owned_files: int
    unowned_files: int
    coverage_percent: float
    owner_distribution: Dict[str, int] = field(default_factory=dict)
    unowned_file_paths: List[str] = field(default_factory=list)
    rule_usage_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "owned_files": self.owned_files,
            "unowned_files": self.unowned_files,
            "coverage_percent": round(self.coverage_percent, 2),
            "owner_distribution": self.owner_distribution,
            "unowned_sample": self.unowned_file_paths[:20],
            "rule_usage_counts": self.rule_usage_counts,
        }

    def to_text(self) -> str:
        lines = [
            "==================================================",
            "           CODEOWNERS AUDIT REPORT                ",
            "==================================================",
            f"Total Files Scanned : {self.total_files}",
            f"Owned Files         : {self.owned_files} ({self.coverage_percent:.1f}%)",
            f"Unowned Files       : {self.unowned_files} ({100.0 - self.coverage_percent:.1f}%)",
            "",
            "--- Top Owners Breakdown ---",
        ]
        sorted_owners = sorted(self.owner_distribution.items(), key=lambda x: x[1], reverse=True)
        for owner, count in sorted_owners[:10]:
            pct = (count / self.total_files * 100) if self.total_files else 0
            lines.append(f"  {owner.ljust(30)} : {count:4d} files ({pct:5.1f}%)")

        if self.unowned_file_paths:
            lines.append("")
            lines.append("--- Unowned Files (First 10) ---")
            for p in self.unowned_file_paths[:10]:
                lines.append(f"  [UNOWNED] {p}")
            if len(self.unowned_file_paths) > 10:
                lines.append(f"  ... and {len(self.unowned_file_paths) - 10} more.")

        lines.append("==================================================")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        lines = [
            "## 🛡️ CODEOWNERS Audit Summary",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| **Total Files** | `{self.total_files}` |",
            f"| **Owned Files** | `{self.owned_files}` (`{self.coverage_percent:.1f}%`) |",
            f"| **Unowned Files** | `{self.unowned_files}` |",
            "",
            "### 👥 Top Owners",
            "",
            "| Owner | Files Owned | Coverage Share |",
            "| :--- | :--- | :--- |",
        ]
        sorted_owners = sorted(self.owner_distribution.items(), key=lambda x: x[1], reverse=True)
        for owner, count in sorted_owners[:10]:
            pct = (count / self.total_files * 100) if self.total_files else 0
            lines.append(f"| `{owner}` | `{count}` | `{pct:.1f}%` |")

        if self.unowned_file_paths:
            lines.append("")
            lines.append("<details><summary><b>⚠️ Unowned Files (" + str(len(self.unowned_file_paths)) + ")</b></summary>")
            lines.append("")
            lines.append("```")
            for p in self.unowned_file_paths[:25]:
                lines.append(p)
            if len(self.unowned_file_paths) > 25:
                lines.append(f"... and {len(self.unowned_file_paths) - 25} more")
            lines.append("```")
            lines.append("</details>")

        return "\n".join(lines)


def audit_ownership(
    codeowners_content: str | ParsedCodeowners,
    files_list: Optional[Sequence[str]] = None,
    repo_dir: Optional[str | Path] = None,
) -> OwnershipAuditReport:
    """Calculate complete ownership statistics over a repository's files."""
    if isinstance(codeowners_content, str):
        parsed = parse_codeowners(codeowners_content)
    else:
        parsed = codeowners_content

    matcher = CodeownersMatcher(parsed)

    files: List[str] = []
    if files_list is not None:
        files = [normalize_repo_path(f) for f in files_list]
    elif repo_dir:
        rdir = Path(repo_dir)
        ignored = {".git", ".pytest_cache", ".mypy_cache", "__pycache__", "node_modules", "venv", ".venv"}
        for root, dirs, fnames in os.walk(rdir):
            dirs[:] = [d for d in dirs if d not in ignored]
            rel_dir = os.path.relpath(root, rdir)
            for fn in fnames:
                rel = fn if rel_dir == "." else os.path.join(rel_dir, fn)
                files.append(normalize_repo_path(rel))

    total = len(files)
    owned_count = 0
    unowned_paths: List[str] = []
    owner_dist: Dict[str, int] = {}
    rule_usage: Dict[str, int] = {}

    for f in files:
        rule = matcher.find_matching_rule(f)
        if rule and rule.owners:
            owned_count += 1
            rule_usage[rule.pattern] = rule_usage.get(rule.pattern, 0) + 1
            for owner in rule.owners:
                owner_dist[owner] = owner_dist.get(owner, 0) + 1
        else:
            unowned_paths.append(f)

    cov = (owned_count / total * 100.0) if total > 0 else 100.0

    return OwnershipAuditReport(
        total_files=total,
        owned_files=owned_count,
        unowned_files=len(unowned_paths),
        coverage_percent=cov,
        owner_distribution=owner_dist,
        unowned_file_paths=unowned_paths,
        rule_usage_counts=rule_usage,
    )
