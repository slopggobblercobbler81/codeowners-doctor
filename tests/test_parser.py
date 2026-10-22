"""Tests for CODEOWNERS parser."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from codeowners_doctor.models import LineType, OwnerKind
from codeowners_doctor.parser import CodeOwnersParser, split_codeowners_line


def test_split_simple_rule():
    line = "*.js @alice @org/frontend"
    pattern, owners, comment = split_codeowners_line(line)
    assert pattern == "*.js"
    assert owners == ["@alice", "@org/frontend"]
    assert comment is None


def test_split_with_inline_comment():
    line = "/docs/* @writer # Documentation team lead"
    pattern, owners, comment = split_codeowners_line(line)
    assert pattern == "/docs/*"
    assert owners == ["@writer"]
    assert comment == "Documentation team lead"


def test_split_escaped_spaces():
    line = r"special\ folder/my\ script.py @developer"
    pattern, owners, comment = split_codeowners_line(line)
    assert pattern == r"special\ folder/my\ script.py"
    assert owners == ["@developer"]


def test_split_empty_and_comment():
    assert split_codeowners_line("") == (None, [], None)
    assert split_codeowners_line("   \t  ") == (None, [], None)
    p, o, c = split_codeowners_line("# Just a comment")
    assert p is None
    assert o == []
    assert c == "Just a comment"


def test_parse_text_full():
    sample = """# Global ownership
* @octocat

# Documentation
/docs/ @docs-team docs-lead@example.com

[Frontend Section]
/src/ui/ @frontend-team # inline note
"""
    lines = CodeOwnersParser.parse_text(sample)
    assert len(lines) == 8

    # Line 1: Comment
    assert lines[0].line_type == LineType.COMMENT
    assert lines[0].comment == "Global ownership"

    # Line 2: Rule
    assert lines[1].line_type == LineType.RULE
    assert lines[1].pattern == "*"
    assert lines[1].owners == ["@octocat"]
    parsed_owners = lines[1].parsed_owners
    assert len(parsed_owners) == 1
    assert parsed_owners[0].kind == OwnerKind.USER
    assert parsed_owners[0].name == "octocat"

    # Line 3: Empty
    assert lines[2].line_type == LineType.EMPTY

    # Line 4: Comment
    assert lines[3].line_type == LineType.COMMENT

    # Line 5: Rule
    assert lines[4].line_type == LineType.RULE
    assert lines[4].pattern == "/docs/"
    assert lines[4].owners == ["@docs-team", "docs-lead@example.com"]
    owners = lines[4].parsed_owners
    assert owners[0].kind == OwnerKind.USER
    assert owners[1].kind == OwnerKind.EMAIL

    # Line 6: Empty
    assert lines[5].line_type == LineType.EMPTY

    # Line 7: Section
    assert lines[6].line_type == LineType.SECTION
    assert lines[6].section == "Frontend Section"

    # Line 8: Rule inside section
    assert lines[7].line_type == LineType.RULE
    assert lines[7].section == "Frontend Section"
    assert lines[7].pattern == "/src/ui/"
    assert lines[7].owners == ["@frontend-team"]
    assert lines[7].comment == "inline note"


def test_discover_codeowners_precedence():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        gh_dir = root / ".github"
        gh_dir.mkdir()
        docs_dir = root / "docs"
        docs_dir.mkdir()

        (gh_dir / "CODEOWNERS").write_text("* @gh-owner", encoding="utf-8")
        (root / "CODEOWNERS").write_text("* @root-owner", encoding="utf-8")
        (docs_dir / "CODEOWNERS").write_text("* @docs-owner", encoding="utf-8")

        discovered = CodeOwnersParser.discover_codeowners(root)
        assert len(discovered) == 3
        # First must be .github/CODEOWNERS
        assert discovered[0] == gh_dir / "CODEOWNERS"
        assert discovered[1] == root / "CODEOWNERS"
        assert discovered[2] == docs_dir / "CODEOWNERS"
