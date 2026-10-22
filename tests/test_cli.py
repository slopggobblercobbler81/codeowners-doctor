"""Unit and integration tests for CLI commands."""

import json
import pytest
from codeowners_doctor.cli import main, find_codeowners_file


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "codeowners-doctor 0.1.0" in captured.out or "codeowners-doctor 0.1.0" in captured.err


def test_cli_check_clean(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* @maintainers\n/docs/ @docs\n", encoding="utf-8")

    code = main(["check", str(f), "--no-dead-rules", "--no-critical-check"])
    assert code == 0
    captured = capsys.readouterr()
    assert "No issues found" in captured.out


def test_cli_check_error(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* invalid_owner_missing_at\n", encoding="utf-8")

    code = main(["check", str(f), "--no-dead-rules", "--no-critical-check"])
    assert code == 1
    captured = capsys.readouterr()
    assert "[ERROR]" in captured.out
    assert "Invalid owner format" in captured.out


def test_cli_check_json(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* @maintainers\n", encoding="utf-8")

    code = main(["check", str(f), "--no-dead-rules", "--no-critical-check", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["is_clean"] is True
    assert data["total_rules"] == 1


def test_cli_check_sarif(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* bad_owner\n", encoding="utf-8")

    code = main(["check", str(f), "--no-dead-rules", "--no-critical-check", "--sarif"])
    assert code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["version"] == "2.1.0"
    assert len(data["runs"]) == 1


def test_cli_check_strict_flag(tmp_path):
    f = tmp_path / "CODEOWNERS"
    # Rule with duplicate owner causes warning
    f.write_text("*.js @alice @bob @alice\n", encoding="utf-8")

    # Without strict: exit 0 because only warning
    assert main(["check", str(f), "--no-dead-rules", "--no-critical-check"]) == 0
    # With strict: exit 1 on warning
    assert main(["check", str(f), "--no-dead-rules", "--no-critical-check", "--strict"]) == 1


def test_cli_who_command(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* @global\n/src/auth/ @security\n", encoding="utf-8")

    code = main(["who", "src/auth/jwt.py", "--file", str(f)])
    assert code == 0
    captured = capsys.readouterr()
    assert "@security" in captured.out
    assert "/src/auth/" in captured.out


def test_cli_who_json(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* @global\n", encoding="utf-8")

    code = main(["who", "index.js", "--file", str(f), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["path"] == "index.js"
    assert data["owned"] is True
    assert data["owners"] == ["@global"]


def test_cli_audit_command(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* @team\n", encoding="utf-8")
    (tmp_path / "file1.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "file2.py").write_text("y = 2", encoding="utf-8")

    code = main(["audit", "--file", str(f), "--repo", str(tmp_path), "--format", "markdown"])
    assert code == 0
    captured = capsys.readouterr()
    assert "CODEOWNERS Audit Summary" in captured.out
    assert "100.0%" in captured.out


def test_cli_audit_min_coverage_fail(tmp_path):
    f = tmp_path / "CODEOWNERS"
    f.write_text("/only_this/ @team\n", encoding="utf-8")
    (tmp_path / "file1.py").write_text("x = 1", encoding="utf-8")

    # Coverage will be 0% since file1.py does not match /only_this/
    code = main(["audit", "--file", str(f), "--repo", str(tmp_path), "--min-coverage", "80"])
    assert code == 1


def test_cli_format_command(tmp_path):
    f = tmp_path / "CODEOWNERS"
    f.write_text("*.js    @alice   @bob   \n", encoding="utf-8")

    out_file = tmp_path / "FORMATTED"
    code = main(["format", "--file", str(f), "-o", str(out_file)])
    assert code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert "@alice @bob" in content


def test_cli_init_command(tmp_path):
    out_target = tmp_path / ".github" / "CODEOWNERS"
    code = main(["init", "--out", str(out_target), "--default-owner", "@my-team/leads"])
    assert code == 0
    assert out_target.exists()
    assert "@my-team/leads" in out_target.read_text(encoding="utf-8")


def test_find_codeowners_file(tmp_path):
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    co_file = github_dir / "CODEOWNERS"
    co_file.write_text("* @owner\n")

    found = find_codeowners_file(start_dir=tmp_path)
    assert found == co_file


def test_cli_check_missing_file(capsys):
    ret = main(["check", "nonexistent/CODEOWNERS"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Could not locate CODEOWNERS file" in captured.err


def test_cli_default_command_without_args(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ret = main([])
    assert ret == 1


def test_cli_who_missing_file(capsys):
    ret = main(["who", "src/file.py", "--file", "nonexistent/CODEOWNERS"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Could not locate CODEOWNERS file" in captured.err


def test_cli_who_unowned_and_explicit(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* @maintainer\n/unowned/path.txt\n", encoding="utf-8")

    # Explicitly unowned
    ret = main(["who", "unowned/path.txt", "--file", str(f)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Explicitly unowned" in captured.out

    # Missing altogether (empty CODEOWNERS)
    f2 = tmp_path / "EMPTY_CODEOWNERS"
    f2.write_text("# Only comments\n", encoding="utf-8")
    ret2 = main(["who", "other.py", "--file", str(f2)])
    assert ret2 == 0
    captured2 = capsys.readouterr()
    assert "Unowned (no matching rule)" in captured2.out


def test_cli_audit_missing_file(capsys):
    ret = main(["audit", "--file", "nonexistent/CODEOWNERS"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Could not locate CODEOWNERS file" in captured.err


def test_cli_audit_text_and_json(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("* @maintainer\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print(1)", encoding="utf-8")

    ret_txt = main(["audit", "--file", str(f), "--repo", str(tmp_path), "--format", "text"])
    assert ret_txt == 0
    captured_txt = capsys.readouterr()
    assert "CODEOWNERS AUDIT REPORT" in captured_txt.out

    ret_json = main(["audit", "--file", str(f), "--repo", str(tmp_path), "--format", "json"])
    assert ret_json == 0
    captured_json = capsys.readouterr()
    data = json.loads(captured_json.out)
    assert data["total_files"] >= 1


def test_cli_format_missing_file(capsys):
    ret = main(["format", "--file", "nonexistent/CODEOWNERS"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Could not locate CODEOWNERS file" in captured.err


def test_cli_format_in_place_and_stdout(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("*.py   @python   \n", encoding="utf-8")

    # stdout format
    ret = main(["format", "--file", str(f)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "*.py" in captured.out
    assert "@python" in captured.out

    # in-place format
    ret2 = main(["format", "--file", str(f), "-i"])
    assert ret2 == 0
    assert f.read_text(encoding="utf-8").endswith("\n")


def test_cli_fix_command(tmp_path, capsys):
    f = tmp_path / "CODEOWNERS"
    f.write_text("*.js   @js-team   \n", encoding="utf-8")
    ret = main(["fix", "--file", str(f)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Formatted and saved" in captured.out


def test_cli_init_exists_error_and_force(tmp_path, capsys):
    target = tmp_path / "CODEOWNERS"
    target.write_text("pre-existing", encoding="utf-8")

    # Without force
    ret = main(["init", "--out", str(target)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "already exists" in captured.err

    # With force
    ret2 = main(["init", "--out", str(target), "--force"])
    assert ret2 == 0
    assert "@org/maintainers" in target.read_text(encoding="utf-8")
