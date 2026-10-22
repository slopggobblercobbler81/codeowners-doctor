"""End-to-end integration tests for codeowners-doctor CLI."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from codeowners_doctor.cli import main


def test_cli_check_success(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("* @slopggobblercobbler81\n", encoding="utf-8")
        test_file = root / "app.py"
        test_file.write_text("print('hello')", encoding="utf-8")

        ret = main(["check", str(codeowners), "--root", str(root)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "All checks passed" in captured.out


def test_cli_check_json_output(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("*.js @js-team\n*.py invalid_owner\n", encoding="utf-8")

        ret = main(["check", str(codeowners), "--root", str(root), "--format", "json"])
        assert ret == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["passed"] is False
        assert any(d["code"] == "E003" for d in data["diagnostics"])


def test_cli_check_strict_fails_on_warning(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("*.js @alice @bob @alice\n", encoding="utf-8")
        (root / "app.js").write_text("// js")

        # Without strict -> warning allows 0 exit
        ret_normal = main(["check", str(codeowners), "--root", str(root)])
        assert ret_normal == 0

        # With strict -> warning fails with 1
        ret_strict = main(["check", str(codeowners), "--root", str(root), "--strict"])
        assert ret_strict == 1


def test_cli_who_command(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("src/**/*.ts @frontend\n*.py @backend\n", encoding="utf-8")

        # Matched file
        ret = main(["who", "src/views/main.ts", "-p", str(codeowners)])
        assert ret == 0
        captured = capsys.readouterr()
        assert "@frontend" in captured.out

        # Unmatched file
        ret_unmatched = main(["who", "docs/index.html", "-p", str(codeowners)])
        assert ret_unmatched == 1
        captured = capsys.readouterr()
        assert "unowned" in captured.out


def test_cli_unowned_command(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("src/* @team\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "index.js").write_text("...")
        (root / "untracked.txt").write_text("orphan")

        ret = main(["unowned", "-p", str(codeowners), "-r", str(root)])
        assert ret == 1
        captured = capsys.readouterr()
        assert "untracked.txt" in captured.out


def test_cli_format_command(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        codeowners = root / "CODEOWNERS"
        codeowners.write_text("*    @alice   @bob   @alice\n", encoding="utf-8")

        # Check mode before write
        ret_check = main(["format", str(codeowners), "--check"])
        assert ret_check == 1

        # Write mode
        ret_write = main(["format", str(codeowners), "--write"])
        assert ret_write == 0

        # Check mode after write
        ret_check2 = main(["format", str(codeowners), "--check"])
        assert ret_check2 == 0

        content = codeowners.read_text(encoding="utf-8")
        assert content.count("@alice") == 1


def test_cli_locate_command(capsys):
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        gh_dir = root / ".github"
        gh_dir.mkdir()
        (gh_dir / "CODEOWNERS").write_text("* @owner")

        ret = main(["locate", "-r", str(root)])
        assert ret == 0
        captured = capsys.readouterr()
        assert ".github/CODEOWNERS" in captured.out.replace("\\", "/")


def test_cli_missing_codeowners(capsys):
    with TemporaryDirectory() as tmpdir:
        ret = main(["check", "-r", str(tmpdir)])
        assert ret == 2
        captured = capsys.readouterr()
        assert "No CODEOWNERS file found" in captured.err
