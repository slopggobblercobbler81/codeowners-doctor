"""Tests for CODEOWNERS linter and diagnostics."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from codeowners_doctor.linter import CodeOwnersLinter
from codeowners_doctor.models import DiagnosticSeverity
from codeowners_doctor.parser import CodeOwnersParser


def test_linter_empty_rule_and_invalid_owner():
    content = """
# Missing owner
*.py

# Invalid owner token
*.js @alice not_an_owner

# Valid rule
*.go @gopher
"""
    lines = CodeOwnersParser.parse_text(content)
    linter = CodeOwnersLinter(lines)
    diagnostics = linter.run_all()

    codes = [d.code for d in diagnostics]
    assert "E002" in codes  # Missing owner
    assert "E003" in codes  # Invalid owner token


def test_linter_duplicate_owners():
    content = "*.ts @alice @bob @alice @Bob"
    lines = CodeOwnersParser.parse_text(content)
    linter = CodeOwnersLinter(lines)
    diagnostics = linter.run_all()

    dup_diags = [d for d in diagnostics if d.code == "W001"]
    assert len(dup_diags) == 1
    assert "Duplicate owner" in dup_diags[0].message


def test_linter_redundant_wildcards():
    content = """
./scripts/* @devops
src/**/**/main.py @lead
"""
    lines = CodeOwnersParser.parse_text(content)
    linter = CodeOwnersLinter(lines)
    diagnostics = linter.run_all()

    w005 = [d for d in diagnostics if d.code == "W005"]
    assert len(w005) == 2


def test_linter_shadowed_rules():
    content = """
/docs/* @writer
/docs/* @lead-writer
*.py @python-dev
* @all-powerful
"""
    lines = CodeOwnersParser.parse_text(content)
    linter = CodeOwnersLinter(lines)
    diagnostics = linter.run_all()

    w002 = [d for d in diagnostics if d.code == "W002"]
    # 1. line 2 /docs/* is shadowed by line 3 /docs/*
    # 2. line 4 *.py is shadowed by line 5 catch-all '*'
    assert len(w002) >= 2


def test_linter_orphan_patterns_and_unowned():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir()
        (root / "src" / "index.js").write_text("console.log('hi');")
        (root / "docs").mkdir()
        (root / "docs" / "readme.md").write_text("# Doc")
        (root / "secret.key").write_text("xyz")

        codeowners = """
# Existing
src/*.js @js-team
docs/* @docs-team

# Orphan pattern (no ruby files exist)
*.rb @ruby-team
"""
        lines = CodeOwnersParser.parse_text(codeowners)
        linter = CodeOwnersLinter(lines, repo_root=root)
        diagnostics = linter.run_all(check_unowned=True)

        orphan_diags = [d for d in diagnostics if d.code == "W003"]
        assert len(orphan_diags) == 1
        assert "*.rb" in orphan_diags[0].message

        unowned_diags = [d for d in diagnostics if d.code == "W004"]
        assert len(unowned_diags) == 1
        assert "secret.key" in unowned_diags[0].message
