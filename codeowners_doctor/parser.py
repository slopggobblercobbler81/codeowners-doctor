"""Parser for CODEOWNERS files."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from codeowners_doctor.models import CodeOwnersLine, LineType


SECTION_RE = re.compile(r"^(\^)?\[([^\]]+)\](?:\[(\d+)\])?\s*(?:#.*)?$")


def split_codeowners_line(line: str) -> Tuple[Optional[str], List[str], Optional[str]]:
    """Splits a CODEOWNERS rule line into pattern, owners, and inline comment.
    
    Handles escaped spaces in pattern (e.g. `path/to/my\\ file.txt`).
    """
    stripped = line.strip()
    if not stripped:
        return None, [], None

    # Check for whole-line comment
    if stripped.startswith("#"):
        return None, [], stripped[1:].strip()

    # Tokenize preserving escaped spaces
    tokens: List[str] = []
    current: List[str] = []
    escaped = False
    comment_part: Optional[str] = None

    i = 0
    while i < len(line):
        ch = line[i]

        if escaped:
            current.append(ch)
            escaped = False
            i += 1
            continue

        if ch == "\\":
            escaped = True
            current.append(ch)
            i += 1
            continue

        if ch == "#":
            # If we are starting a token or following whitespace, it's a comment
            if not current or line[i - 1].isspace():
                comment_part = line[i + 1 :].strip()
                break

        if ch.isspace():
            if current:
                token = "".join(current)
                tokens.append(token)
                current = []
        else:
            current.append(ch)

        i += 1

    if current:
        tokens.append("".join(current))

    if not tokens:
        return None, [], comment_part

    pattern = tokens[0]
    owners = tokens[1:]
    return pattern, owners, comment_part


class CodeOwnersParser:
    """Parses CODEOWNERS file into structured lines."""

    STANDARD_LOCATIONS = [
        ".github/CODEOWNERS",
        "CODEOWNERS",
        "docs/CODEOWNERS",
        ".gitlab/CODEOWNERS",
    ]

    @classmethod
    def discover_codeowners(cls, repo_root: Path) -> List[Path]:
        """Discovers all candidate CODEOWNERS files in priority order."""
        found = []
        for loc in cls.STANDARD_LOCATIONS:
            path = repo_root / loc
            if path.is_file():
                found.append(path)
        return found

    @classmethod
    def parse_text(cls, content: str) -> List[CodeOwnersLine]:
        """Parses the text content of a CODEOWNERS file."""
        lines = content.splitlines()
        parsed: List[CodeOwnersLine] = []
        current_section: Optional[str] = None

        for line_num, raw in enumerate(lines, start=1):
            stripped = raw.strip()

            # Empty line
            if not stripped:
                parsed.append(
                    CodeOwnersLine(
                        line_number=line_num,
                        raw=raw,
                        line_type=LineType.EMPTY,
                        section=current_section,
                    )
                )
                continue

            # Full line comment
            if stripped.startswith("#"):
                comment_body = stripped[1:].strip()
                parsed.append(
                    CodeOwnersLine(
                        line_number=line_num,
                        raw=raw,
                        line_type=LineType.COMMENT,
                        comment=comment_body,
                        section=current_section,
                    )
                )
                continue

            # GitLab Section header: [Section Name] or ^[Section Name] or [Section][2]
            sec_match = SECTION_RE.match(stripped)
            if sec_match:
                section_name = sec_match.group(2).strip()
                current_section = section_name
                parsed.append(
                    CodeOwnersLine(
                        line_number=line_num,
                        raw=raw,
                        line_type=LineType.SECTION,
                        section=section_name,
                    )
                )
                continue

            # Regular rule line
            pattern, owners, comment = split_codeowners_line(raw)
            parsed.append(
                CodeOwnersLine(
                    line_number=line_num,
                    raw=raw,
                    line_type=LineType.RULE,
                    pattern=pattern,
                    owners=owners,
                    section=current_section,
                    comment=comment,
                )
            )

        return parsed

    @classmethod
    def parse_file(cls, path: Path) -> List[CodeOwnersLine]:
        """Reads and parses a CODEOWNERS file."""
        content = path.read_text(encoding="utf-8")
        return cls.parse_text(content)
