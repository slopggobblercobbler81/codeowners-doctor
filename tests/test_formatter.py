"""Unit tests for CODEOWNERS formatter."""

import pytest
from codeowners_doctor.formatter import format_codeowners


def test_format_codeowners_alignment():
    raw = """
* @global
/src/components/button.tsx @ui-team
/docs/ @docs
"""
    formatted = format_codeowners(raw, align_columns=True)
    lines = [line for line in formatted.splitlines() if line]

    assert len(lines) == 3
    # Check that owners start after uniform padding
    assert lines[0].startswith("* ")
    assert "@global" in lines[0]
    assert "@ui-team" in lines[1]
    assert "@docs" in lines[2]


def test_format_codeowners_dedup_owners():
    raw = "*.js @alice @bob @alice"
    formatted = format_codeowners(raw, dedup_owners=True)
    assert formatted.strip().endswith("@alice @bob")


def test_format_codeowners_remove_dead():
    raw = """
/exists.py @alice
/dead.py @bob
"""
    repo_files = ["exists.py", "other.txt"]
    formatted = format_codeowners(raw, repo_files=repo_files, remove_dead=True)

    assert "exists.py" in formatted
    assert "dead.py" not in formatted


def test_format_empty():
    assert format_codeowners("") == ""


def test_format_no_align_and_inline_comments():
    raw = """# Header comment
*.py @python-team # primary language
/docs/ # unowned docs
"""
    formatted = format_codeowners(raw, align_columns=False, dedup_owners=False)
    assert "# Header comment" in formatted
    assert "*.py  @python-team  # primary language" in formatted
    assert "/docs/" in formatted
