"""Data models for codeowners-doctor."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class LineType(str, Enum):
    RULE = "rule"
    SECTION = "section"
    COMMENT = "comment"
    EMPTY = "empty"


class OwnerKind(str, Enum):
    USER = "user"
    TEAM = "team"
    EMAIL = "email"
    INVALID = "invalid"


@dataclass
class Owner:
    raw: str
    kind: OwnerKind
    name: str

    @classmethod
    def parse(cls, token: str) -> Owner:
        token = token.strip()
        if token.startswith("@"):
            body = token[1:]
            if "/" in body:
                org, team = body.split("/", 1)
                if org and team and not any(c in body for c in " \t\r\n"):
                    return cls(raw=token, kind=OwnerKind.TEAM, name=body)
            elif body and not any(c in body for c in " \t\r\n/"):
                return cls(raw=token, kind=OwnerKind.USER, name=body)
            return cls(raw=token, kind=OwnerKind.INVALID, name=token)
        elif "@" in token and "." in token.split("@")[-1] and not token.startswith("@"):
            parts = token.split("@")
            if len(parts) == 2 and parts[0] and parts[1]:
                return cls(raw=token, kind=OwnerKind.EMAIL, name=token)
        return cls(raw=token, kind=OwnerKind.INVALID, name=token)


@dataclass
class CodeOwnersLine:
    line_number: int
    raw: str
    line_type: LineType
    pattern: Optional[str] = None
    owners: List[str] = field(default_factory=list)
    section: Optional[str] = None
    comment: Optional[str] = None

    @property
    def parsed_owners(self) -> List[Owner]:
        return [Owner.parse(o) for o in self.owners]


class DiagnosticSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Diagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity
    line_number: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None
    rule_line: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "line_number": self.line_number,
            "column": self.column,
            "suggestion": self.suggestion,
            "rule_line": self.rule_line,
        }


@dataclass
class MatchResult:
    file_path: str
    matched: bool
    rule_line_number: Optional[int] = None
    pattern: Optional[str] = None
    owners: List[str] = field(default_factory=list)
    section: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "matched": self.matched,
            "rule_line_number": self.rule_line_number,
            "pattern": self.pattern,
            "owners": self.owners,
            "section": self.section,
        }
