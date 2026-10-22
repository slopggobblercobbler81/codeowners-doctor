"""Additional tests for codeowners-doctor covering models, matcher edge cases, and CLI options."""
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from codeowners_doctor.__init__ import __version__
from codeowners_doctor.cli import _use_color, main
from codeowners_doctor.matcher import CodeOwnersMatcher, compile_pattern_to_regex
from codeowners_doctor.models import (
    CodeOwnersLine,
    Diagnostic,
    DiagnosticSeverity,
    LineType,
    MatchResult,
    Owner,
    OwnerKind,
)


def test_models_owner_parsing():
    # User
    u = Owner.parse("@alice")
    assert u.kind == OwnerKind.USER
    assert u.name == "alice"

    # Team
    t = Owner.parse("@org/security-team")
    assert t.kind == OwnerKind.TEAM
    assert t.name == "org/security-team"

    # Email
    e = Owner.parse("lead-dev@company.com")
    assert e.kind == OwnerKind.EMAIL
    assert e.name == "lead-dev@company.com"

    # Invalids
    inv1 = Owner.parse("@")
    assert inv1.kind == OwnerKind.INVALID

    inv2 = Owner.parse("@org/")
    assert inv2.kind == OwnerKind.INVALID

    inv3 = OwnerKind.INVALID
    assert Owner.parse("plain_text").kind == inv3

    assert Owner.parse("bad@email").kind == OwnerKind.INVALID


def test_models_to_dict():
    diag = Diagnostic(
        code="E001",
        message="Test error",
        severity=DiagnosticSeverity.ERROR,
        line_number=5,
        column=1,
        suggestion="Fix it",
        rule_line="bad pattern",
    )
    d = diag.to_dict()
    assert d["code"] == "E001"
    assert d["severity"] == "ERROR"
    assert d["line_number"] == 5

    res = MatchResult(
        file_path="src/index.ts",
        matched=True,
        rule_line_number=2,
        pattern="src/*",
        owners=["@devs"],
        section="Frontend",
    )
    rd = res.to_dict()
    assert rd["file_path"] == "src/index.ts"
    assert rd["matched"] is True
    assert rd["section"] == "Frontend"


def test_matcher_advanced_patterns():
    # Escaped space in pattern
    regex_escaped = compile_pattern_to_regex(r"my\ space/file.txt")
    assert regex_escaped.match("my space/file.txt")

    # Character class and negation
    regex_class = compile_pattern_to_regex("docs/[a-z]*.md")
    assert regex_class.match("docs/intro.md")
    assert not regex_class.match("docs/123.md")

    regex_neg = compile_pattern_to_regex("test[!0-9].py")
    assert regex_neg.match("testa.py")
    assert not regex_neg.match("test1.py")

    # Question mark wildcard
    regex_qm = compile_pattern_to_regex("file?.txt")
    assert regex_qm.match("file1.txt")
    assert regex_qm.match("fileA.txt")
    assert not regex_qm.match("file12.txt")

    # Trailing double star
    regex_trailing_ds = compile_pattern_to_regex("docs/**")
    assert regex_trailing_ds.match("docs/api/v1/auth.md")
    assert regex_trailing_ds.match("docs/guide.txt")

    # Leading double star
    regex_leading_ds = compile_pattern_to_regex("**/logs/*.log")
    assert regex_leading_ds.match("logs/app.log")
    assert regex_leading_ds.match("var/logs/app.log")
    assert regex_leading_ds.match("a/b/c/logs/app.log")

    # Match all
    rules = [CodeOwnersLine(1, "*.py @py", LineType.RULE, pattern="*.py", owners=["@py"])]
    matcher = CodeOwnersMatcher(rules)
    all_res = matcher.match_all(["a.py", "b.js"])
    assert all_res["a.py"].matched is True
    assert all_res["b.js"].matched is False


def test_cli_default_invocation(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / ".github" / "CODEOWNERS"
        codeowners.parent.mkdir()
        codeowners.write_text("* @all\n", encoding="utf-8")

        # Running main with no args defaults to check
        cur = os.getcwd()
        try:
            os.chdir(str(root))
            ret = main([])
            assert ret == 0
            captured = capsys.readouterr()
            assert "All checks passed" in captured.out
        finally:
            os.chdir(cur)


def test_cli_multiple_codeowners_warning(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        gh = root / ".github"
        gh.mkdir()
        (gh / "CODEOWNERS").write_text("* @primary\n", encoding="utf-8")
        (root / "CODEOWNERS").write_text("* @secondary\n", encoding="utf-8")

        ret = main(["check", "-r", str(root)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Multiple CODEOWNERS files found" in captured.out
        assert "W006" in captured.out


def test_cli_who_json(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("*.rs @rustaceans\n", encoding="utf-8")

        ret = main(["who", "main.rs", "-p", str(codeowners), "-f", "json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["matched"] is True
        assert "@rustaceans" in data["owners"]


def test_cli_unowned_success_and_json(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("* @global\n", encoding="utf-8")
        (root / "file1.txt").write_text("hello")

        # Text mode 100% coverage
        ret = main(["unowned", "-p", str(codeowners), "-r", str(root)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "100% code ownership coverage" in captured.out

        # JSON mode
        ret_json = main(["unowned", "-p", str(codeowners), "-r", str(root), "-f", "json"])
        assert ret_json == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["unowned_count"] == 0


def test_cli_format_write_and_check(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("*.js     @alice   @bob   @alice\n", encoding="utf-8")

        # Format --check fails when unformatted
        ret_check = main(["format", str(codeowners), "--check"])
        assert ret_check == 1

        # Format --write formats in-place
        ret_write = main(["format", str(codeowners), "--write"])
        assert ret_write == 0
        content = codeowners.read_text(encoding="utf-8")
        assert "@alice @bob\n" in content
        assert "@alice @bob @alice" not in content

        # Format --check passes when formatted
        ret_check2 = main(["format", str(codeowners), "--check"])
        assert ret_check2 == 0

        # Format --write again reports already formatted
        ret_write2 = main(["format", str(codeowners), "--write"])
        assert ret_write2 == 0


def test_cli_locate_missing_and_json(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        ret = main(["locate", "-r", str(root)])
        assert ret == 1
        captured = capsys.readouterr()
        assert "No CODEOWNERS file found" in captured.out

        ret_json = main(["locate", "-r", str(root), "-f", "json"])
        assert ret_json == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["active"] is None
        assert data["found"] == []


def test_use_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert _use_color() is False
