"""Parser for GitHub and GitLab CODEOWNERS files."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)
USERNAME_REGEX = re.compile(
    r"^@[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$"
)
TEAM_REGEX = re.compile(
    r"^@[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}/[a-zA-Z0-9._-]+$"
)
SECTION_REGEX = re.compile(
    r"^(\^)?\[(?P<name>[^\]]+)\](?:\[(?P<approvals>\d+)\])?(?:\s+(?P<owners>.*))?$"
)


@dataclass(frozen=True)
class CodeownersRule:
    """Represents a single pattern-to-owners assignment rule."""
    pattern: str
    owners: Tuple[str, ...]
    line_number: int
    raw_line: str
    comment: Optional[str] = None
    section: Optional[str] = None

    @property
    def is_unowned(self) -> bool:
        """True if the rule explicitly clears ownership for the pattern."""
        return len(self.owners) == 0


@dataclass
class CodeownersSection:
    """Represents a GitLab-style section header."""
    name: str
    line_number: int
    default_owners: Tuple[str, ...] = field(default_factory=tuple)
    optional: bool = False
    approvals_required: Optional[int] = None


@dataclass
class ParsedCodeowners:
    """The complete result of parsing a CODEOWNERS file."""
    rules: List[CodeownersRule]
    sections: List[CodeownersSection]
    raw_lines: List[str]
    comments: List[Tuple[int, str]]  # (line_number, comment_text)


def is_valid_owner(owner: str) -> bool:
    """Check if an owner string is a valid GitHub user, team, or email."""
    if not owner:
        return False
    if owner.startswith("@"):
        if "/" in owner:
            return bool(TEAM_REGEX.match(owner))
        return bool(USERNAME_REGEX.match(owner))
    return bool(EMAIL_REGEX.match(owner))


def _tokenize_line(line: str) -> Tuple[str, List[str], Optional[str]]:
    """Tokenize a CODEOWNERS line into (pattern, owners, trailing_comment).
    
    Handles escaped spaces (\\ ) and escaped hashes (\\#).
    """
    pattern_chars: List[str] = []
    i = 0
    n = len(line)

    # Skip leading whitespace
    while i < n and line[i].isspace():
        i += 1

    if i >= n or line[i] == "#":
        return "", [], None

    # Parse pattern
    in_escape = False
    while i < n:
        c = line[i]
        if in_escape:
            pattern_chars.append(c)
            in_escape = False
            i += 1
            continue

        if c == "\\":
            in_escape = True
            i += 1
            continue

        if c.isspace():
            break
        pattern_chars.append(c)
        i += 1

    pattern = "".join(pattern_chars)

    # Parse owners and optional trailing comment
    owners: List[str] = []
    trailing_comment: Optional[str] = None

    while i < n:
        # Skip whitespace
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break

        if line[i] == "#":
            # Trailing comment begins
            trailing_comment = line[i + 1:].strip()
            break

        # Collect owner token
        owner_chars: List[str] = []
        while i < n and not line[i].isspace():
            if line[i] == "#":
                break
            owner_chars.append(line[i])
            i += 1

        token = "".join(owner_chars).strip()
        if token:
            owners.append(token)

    return pattern, owners, trailing_comment


class CodeownersParser:
    """Production parser for CODEOWNERS files."""

    def __init__(self) -> None:
        pass

    def parse(self, content: str) -> ParsedCodeowners:
        """Parse raw text content of a CODEOWNERS file."""
        lines = content.splitlines()
        rules: List[CodeownersRule] = []
        sections: List[CodeownersSection] = []
        comments: List[Tuple[int, str]] = []

        current_section: Optional[str] = None
        current_section_owners: Tuple[str, ...] = ()

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith("#"):
                comments.append((idx, stripped[1:].strip()))
                continue

            # Check if this is a GitLab section header
            section_match = SECTION_REGEX.match(stripped)
            if section_match:
                is_optional = bool(section_match.group(1))
                sec_name = section_match.group("name").strip()
                approvals_str = section_match.group("approvals")
                approvals = int(approvals_str) if approvals_str else None
                owners_raw = section_match.group("owners")
                sec_owners: List[str] = []
                if owners_raw:
                    for o in owners_raw.split():
                        o = o.strip()
                        if o and not o.startswith("#"):
                            sec_owners.append(o)

                current_section = sec_name
                current_section_owners = tuple(sec_owners)
                sections.append(
                    CodeownersSection(
                        name=sec_name,
                        line_number=idx,
                        default_owners=current_section_owners,
                        optional=is_optional,
                        approvals_required=approvals,
                    )
                )
                continue

            pattern, owners, trailing_comment = _tokenize_line(line)
            if not pattern:
                continue

            # If rule has no explicit owners but section has default owners, assign section owners
            final_owners = tuple(owners) if owners else current_section_owners

            rules.append(
                CodeownersRule(
                    pattern=pattern,
                    owners=final_owners,
                    line_number=idx,
                    raw_line=line,
                    comment=trailing_comment,
                    section=current_section,
                )
            )

        return ParsedCodeowners(
            rules=rules,
            sections=sections,
            raw_lines=lines,
            comments=comments,
        )


def parse_codeowners(content: str) -> ParsedCodeowners:
    """Helper shortcut to parse CODEOWNERS content."""
    return CodeownersParser().parse(content)
