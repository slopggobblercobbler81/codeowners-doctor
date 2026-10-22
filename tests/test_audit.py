"""Unit tests for repository ownership auditing."""

import pytest
from codeowners_doctor.audit import audit_ownership


def test_audit_ownership_metrics():
    codeowners = """
* @default-team
/docs/ @docs-team
/src/ @core-team
/unowned/
"""
    files = [
        "README.md",
        "docs/intro.md",
        "src/app.py",
        "unowned/temp.txt",
    ]

    report = audit_ownership(codeowners, files_list=files)

    assert report.total_files == 4
    assert report.owned_files == 3
    assert report.unowned_files == 1
    assert report.coverage_percent == 75.0
    assert "unowned/temp.txt" in report.unowned_file_paths

    # Owner distribution
    assert report.owner_distribution["@default-team"] == 1
    assert report.owner_distribution["@docs-team"] == 1
    assert report.owner_distribution["@core-team"] == 1


def test_audit_reports_export():
    codeowners = "* @maintainers"
    files = ["main.py", "test.py"]
    report = audit_ownership(codeowners, files_list=files)

    # Text report
    txt = report.to_text()
    assert "CODEOWNERS AUDIT REPORT" in txt
    assert "100.0%" in txt

    # Markdown report
    md = report.to_markdown()
    assert "## 🛡️ CODEOWNERS Audit Summary" in md
    assert "| `main.py`" not in md  # 100% owned, so no unowned list

    # Dict / JSON
    d = report.to_dict()
    assert d["total_files"] == 2
    assert d["coverage_percent"] == 100.0


def test_audit_repo_dir_walk(tmp_path):
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "mod.py").write_text("a = 1", encoding="utf-8")
    (tmp_path / "root.txt").write_text("hello", encoding="utf-8")

    report = audit_ownership("/pkg/ @pkg-team", repo_dir=tmp_path)
    assert report.total_files == 2
    assert report.owned_files == 1
    assert report.unowned_files == 1


def test_audit_large_unowned_formatting():
    # Test unowned formatting when > 10 files and > 25 files
    unowned_files = [f"file_{i}.txt" for i in range(30)]
    report = audit_ownership("/only_one.txt @lead", files_list=unowned_files)
    assert report.unowned_files == 30

    txt = report.to_text()
    assert "and 20 more" in txt

    md = report.to_markdown()
    assert "and 5 more" in md


def test_audit_empty_files():
    report = audit_ownership("* @team", files_list=[])
    assert report.total_files == 0
    assert report.coverage_percent == 100.0
