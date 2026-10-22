"""Formatter for CODEOWNERS files."""
from __future__ import annotations

from typing import List, Tuple

from codeowners_doctor.models import CodeOwnersLine, LineType
from codeowners_doctor.parser import CodeOwnersParser


class CodeOwnersFormatter:
    """Formats CODEOWNERS files with consistent alignment, deduplication, and spacing."""

    @staticmethod
    def deduplicate_owners(owners: List[str]) -> List[str]:
        """Removes duplicate owners preserving original order."""
        seen = set()
        deduped = []
        for o in owners:
            norm = o.lower()
            if norm not in seen:
                seen.add(norm)
                deduped.append(o)
        return deduped

    @classmethod
    def format_lines(cls, lines: List[CodeOwnersLine], min_column: int = 28) -> str:
        """Formats parsed lines into a clean, aligned CODEOWNERS string."""
        # Calculate maximum pattern width
        max_pattern_len = 0
        for line in lines:
            if line.line_type == LineType.RULE and line.pattern:
                if len(line.pattern) > max_pattern_len:
                    max_pattern_len = len(line.pattern)

        col_width = max(max_pattern_len + 4, min_column)

        formatted_lines: List[str] = []
        prev_empty = False

        for line in lines:
            if line.line_type == LineType.EMPTY:
                if not prev_empty:
                    formatted_lines.append("")
                    prev_empty = True
                continue

            prev_empty = False

            if line.line_type == LineType.COMMENT:
                formatted_lines.append(f"# {line.comment}" if line.comment else "#")
                continue

            if line.line_type == LineType.SECTION:
                formatted_lines.append(f"[{line.section}]")
                continue

            if line.line_type == LineType.RULE and line.pattern:
                deduped_owners = cls.deduplicate_owners(line.owners)
                owners_str = " ".join(deduped_owners)

                if owners_str:
                    rule_str = f"{line.pattern:<{col_width}} {owners_str}"
                else:
                    rule_str = line.pattern

                if line.comment:
                    rule_str = f"{rule_str}  # {line.comment}"

                formatted_lines.append(rule_str.rstrip())

        # Ensure trailing newline
        return "\n".join(formatted_lines).rstrip() + "\n"

    @classmethod
    def format_text(cls, text: str) -> str:
        """Parses text and formats it."""
        lines = CodeOwnersParser.parse_text(text)
        return cls.format_lines(lines)

    @classmethod
    def check_text(cls, text: str) -> Tuple[bool, str]:
        """Returns True if text is already formatted, plus the formatted string."""
        formatted = cls.format_text(text)
        is_formatted = text.strip() == formatted.strip()
        return is_formatted, formatted
