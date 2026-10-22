"""Unit tests for CODEOWNERS parser."""

import pytest
from codeowners_doctor.parser import (
    CodeownersParser,
    is_valid_owner,
    parse_codeowners,
    _tokenize_line,
)


def test_is_valid_owner():
    # Valid handles
    assert is_valid_owner("@alice")
    assert is_valid_owner("@alice-123")
    assert is_valid_owner("@org/backend-team")
    assert is_valid_owner("@org/team.core")
    assert is_valid_owner("alice@example.com")
    assert is_valid_owner("first.last+tag@sub.domain.co")

    # Invalid handles
    assert not is_valid_owner("")
    assert not is_valid_owner("alice")  # missing @ or not email
    assert not is_valid_owner("@")
    assert not is_valid_owner("not an email@")
    assert not is_valid_owner("@org//team")


def test_tokenize_line_basic():
    pattern, owners, comment = _tokenize_line("*.js @alice @bob")
    assert pattern == "*.js"
    assert owners == ["@alice", "@bob"]
    assert comment is None


def test_tokenize_line_escaped_spaces():
    pattern, owners, comment = _tokenize_line(r"docs/my\ file.md @alice # notes")
    assert pattern == "docs/my file.md"
    assert owners == ["@alice"]
    assert comment == "notes"


def test_tokenize_line_comment_only():
    pattern, owners, comment = _tokenize_line("# This is a comment")
    assert pattern == ""
    assert owners == []
    assert comment is None


def test_tokenize_line_empty():
    pattern, owners, comment = _tokenize_line("   \t  ")
    assert pattern == ""
    assert owners == []
    assert comment is None


def test_parse_codeowners_standard():
    content = """# Global default
* @global-owner

# Frontend
/frontend/ @frontend-team
*.tsx @frontend-team @alice

# Explicitly unowned
/vendor/
"""
    parsed = parse_codeowners(content)
    assert len(parsed.rules) == 4
    assert len(parsed.comments) >= 3

    assert parsed.rules[0].pattern == "*"
    assert parsed.rules[0].owners == ("@global-owner",)
    assert parsed.rules[0].line_number == 2

    assert parsed.rules[1].pattern == "/frontend/"
    assert parsed.rules[1].owners == ("@frontend-team",)

    assert parsed.rules[2].pattern == "*.tsx"
    assert parsed.rules[2].owners == ("@frontend-team", "@alice")

    assert parsed.rules[3].pattern == "/vendor/"
    assert parsed.rules[3].owners == ()
    assert parsed.rules[3].is_unowned


def test_parse_gitlab_sections():
    content = """[Frontend] @fe-team
/src/ui/
/src/components/ @component-owner

^[Security][2] @sec-lead
/security/
"""
    parsed = parse_codeowners(content)
    assert len(parsed.sections) == 2
    assert len(parsed.rules) == 3

    # Section 1
    s1 = parsed.sections[0]
    assert s1.name == "Frontend"
    assert s1.default_owners == ("@fe-team",)
    assert not s1.optional

    # Rule inheriting default section owner
    assert parsed.rules[0].pattern == "/src/ui/"
    assert parsed.rules[0].owners == ("@fe-team",)
    assert parsed.rules[0].section == "Frontend"

    # Rule overriding section owner
    assert parsed.rules[1].pattern == "/src/components/"
    assert parsed.rules[1].owners == ("@component-owner",)

    # Section 2 (optional with approvals)
    s2 = parsed.sections[1]
    assert s2.name == "Security"
    assert s2.optional is True
    assert s2.approvals_required == 2
    assert parsed.rules[2].section == "Security"
    assert parsed.rules[2].owners == ("@sec-lead",)
