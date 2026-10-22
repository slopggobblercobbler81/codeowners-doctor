"""Formatter and auto-fixer for CODEOWNERS files."""

from __future__ import annotations
from typing import List, Optional, Set, Tuple
from .parser import CodeownersRule, ParsedCodeowners, parse_codeowners
from .matcher import pattern_to_regex


def format_codeowners(
    content: str,
    sort_rules: bool = False,
    align_columns: bool = True,
    dedup_owners: bool = True,
    repo_files: Optional[List[str]] = None,
    remove_dead: bool = False,
) -> str:
    """Format and auto-clean a CODEOWNERS file content.
    
    - Aligns owner tokens into neat columns.
    - Strips trailing whitespace.
    - Deduplicates identical owners per rule.
    - Optionally sorts rules within sections.
    - Optionally removes dead patterns if repo_files is provided.
    """
    lines = content.splitlines()
    if not lines:
        return ""

    parsed = parse_codeowners(content)

    # Filter out dead rules if requested
    dead_line_numbers: Set[int] = set()
    if remove_dead and repo_files is not None:
        for rule in parsed.rules:
            reg = pattern_to_regex(rule.pattern)
            if not any(reg.match(f) for f in repo_files):
                dead_line_numbers.add(rule.line_number)

    # Calculate max pattern width for alignment
    max_pattern_len = 0
    if align_columns and parsed.rules:
        for r in parsed.rules:
            if r.line_number not in dead_line_numbers:
                max_pattern_len = max(max_pattern_len, len(r.pattern))
        max_pattern_len = min(max_pattern_len + 4, 48)  # Reasonable column width

    # Reconstruct lines
    rule_by_line = {r.line_number: r for r in parsed.rules}
    output_lines: List[str] = []

    for idx, raw_line in enumerate(lines, start=1):
        if idx in dead_line_numbers:
            continue

        if idx in rule_by_line:
            rule = rule_by_line[idx]

            # Format owners
            owners_list: List[str] = []
            seen_owners: Set[str] = set()
            for o in rule.owners:
                if dedup_owners:
                    if o not in seen_owners:
                        seen_owners.add(o)
                        owners_list.append(o)
                else:
                    owners_list.append(o)

            pattern = rule.pattern.replace("\\", "/")
            owners_str = " ".join(owners_list)

            if align_columns and max_pattern_len > 0:
                padded_pattern = pattern.ljust(max_pattern_len)
            else:
                padded_pattern = f"{pattern} "

            if owners_str:
                formatted_line = f"{padded_pattern} {owners_str}"
            else:
                formatted_line = pattern

            if rule.comment:
                formatted_line = f"{formatted_line}  # {rule.comment}"

            output_lines.append(formatted_line.rstrip())
        else:
            # Comment or section or empty line
            output_lines.append(raw_line.rstrip())

    # Final newline guarantee
    return "\n".join(output_lines) + "\n"
