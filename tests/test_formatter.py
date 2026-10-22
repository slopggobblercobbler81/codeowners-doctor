"""Tests for CODEOWNERS formatter."""
import pytest

from codeowners_doctor.formatter import CodeOwnersFormatter


def test_deduplicate_owners():
    owners = ["@alice", "@bob", "@alice", "@charlie", "@Bob"]
    result = CodeOwnersFormatter.deduplicate_owners(owners)
    assert result == ["@alice", "@bob", "@charlie"]


def test_format_alignment():
    unformatted = """# Global
*   @root
/really/long/path/to/some/component/file.tsx @frontend-team @frontend-team
*.py @python-dev
"""
    formatted = CodeOwnersFormatter.format_text(unformatted)

    assert "@frontend-team @frontend-team" not in formatted
    assert "@frontend-team" in formatted

    # Check check_text
    is_fmt, _ = CodeOwnersFormatter.check_text(formatted)
    assert is_fmt is True

    is_unfmt, _ = CodeOwnersFormatter.check_text(unformatted)
    assert is_unfmt is False


def test_format_preserves_sections_and_comments():
    text = """# Main comment

[Core Team]
/core/ @core-team

[Docs]
/docs/ @docs-team # inline comment
"""
    formatted = CodeOwnersFormatter.format_text(text)
    assert "# Main comment" in formatted
    assert "[Core Team]" in formatted
    assert "[Docs]" in formatted
    assert "# inline comment" in formatted
