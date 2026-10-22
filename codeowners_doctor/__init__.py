"""codeowners-doctor: Production-grade CODEOWNERS validator, ownership auditor, linter, and formatter for CI/CD."""

__version__ = "0.1.0"

from .parser import CodeownersParser, CodeownersRule, CodeownersSection, parse_codeowners
from .matcher import CodeownersMatcher
from .linter import CodeownersLinter, LintIssue, IssueSeverity
from .formatter import format_codeowners
from .audit import audit_ownership, OwnershipAuditReport
from .generator import generate_codeowners

__all__ = [
    "CodeownersParser",
    "CodeownersRule",
    "CodeownersSection",
    "parse_codeowners",
    "CodeownersMatcher",
    "CodeownersLinter",
    "LintIssue",
    "IssueSeverity",
    "format_codeowners",
    "audit_ownership",
    "OwnershipAuditReport",
    "generate_codeowners",
    "__version__",
]
