"""Unit tests for template generator."""

import pytest
from codeowners_doctor.generator import generate_codeowners


def test_generate_default():
    out = generate_codeowners(default_owner="@my-org/core")
    assert "*                                       @my-org/core" in out
    assert "/.github/workflows/" in out
    assert "Dockerfile" in out
    assert "/docs/" in out


def test_generate_custom_roles(tmp_path):
    # Create fake directory modules
    (tmp_path / "frontend").mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "migrations").mkdir()

    out = generate_codeowners(
        default_owner="@org/core",
        sec_owner="@org/security",
        ops_owner="@org/devops",
        docs_owner="@org/technical-writers",
        repo_dir=tmp_path,
    )

    assert "@org/security" in out
    assert "@org/devops" in out
    assert "@org/technical-writers" in out
    assert "/frontend/" in out
    assert "/backend/" in out
    assert "/migrations/" in out
