"""Tests for CODEOWNERS pattern matching engine."""
import pytest

from codeowners_doctor.matcher import CodeOwnersMatcher, compile_pattern_to_regex
from codeowners_doctor.models import CodeOwnersLine, LineType


def test_compile_pattern_universal_wildcard():
    regex = compile_pattern_to_regex("*")
    assert regex.match("foo.txt")
    assert regex.match("nested/folder/bar.py")
    assert regex.match("a/b/c/d/e")


def test_compile_pattern_root_only():
    regex = compile_pattern_to_regex("/*")
    assert regex.match("foo.txt")
    assert regex.match("LICENSE")
    assert not regex.match("nested/folder.txt")
    assert not regex.match("a/b")


def test_compile_pattern_extension():
    regex = compile_pattern_to_regex("*.js")
    assert regex.match("app.js")
    assert regex.match("src/main.js")
    assert regex.match("src/sub/util.js")
    assert not regex.match("src/main.ts")
    assert not regex.match("app.json")


def test_compile_pattern_directory_trailing_slash():
    # apps/ matches any apps directory
    regex = compile_pattern_to_regex("apps/")
    assert regex.match("apps/foo.py")
    assert regex.match("build/apps/bar.py")
    assert regex.match("sub/level/apps/test.js")

    # /apps/ matches only at root
    regex_root = compile_pattern_to_regex("/apps/")
    assert regex_root.match("apps/foo.py")
    assert not regex_root.match("build/apps/bar.py")


def test_compile_pattern_double_star():
    regex = compile_pattern_to_regex("src/**/models/*.py")
    assert regex.match("src/models/user.py")
    assert regex.match("src/sub/pkg/models/item.py")
    assert not regex.match("other/models/user.py")


def test_matcher_precedence_last_rule_wins():
    rules = [
        CodeOwnersLine(1, "* @global", LineType.RULE, pattern="*", owners=["@global"]),
        CodeOwnersLine(2, "*.js @js-team", LineType.RULE, pattern="*.js", owners=["@js-team"]),
        CodeOwnersLine(3, "/docs/* @docs-team", LineType.RULE, pattern="/docs/*", owners=["@docs-team"]),
        CodeOwnersLine(4, "/docs/architecture.md @architect", LineType.RULE, pattern="/docs/architecture.md", owners=["@architect"]),
    ]
    matcher = CodeOwnersMatcher(rules)

    # General file
    res = matcher.match_file("README.md")
    assert res.matched
    assert res.owners == ["@global"]

    # JS file matches *.js over *
    res = matcher.match_file("src/app.js")
    assert res.matched
    assert res.owners == ["@js-team"]
    assert res.rule_line_number == 2

    # docs file
    res = matcher.match_file("docs/guide.md")
    assert res.matched
    assert res.owners == ["@docs-team"]
    assert res.rule_line_number == 3

    # specific file overrides /docs/*
    res = matcher.match_file("docs/architecture.md")
    assert res.matched
    assert res.owners == ["@architect"]
    assert res.rule_line_number == 4


def test_matcher_windows_paths():
    rules = [
        CodeOwnersLine(1, "src/**/*.py @python-team", LineType.RULE, pattern="src/**/*.py", owners=["@python-team"]),
    ]
    matcher = CodeOwnersMatcher(rules)
    res = matcher.match_file(r"src\services\auth.py")
    assert res.matched
    assert res.owners == ["@python-team"]
    assert res.file_path == "src/services/auth.py"


def test_matcher_no_match():
    rules = [
        CodeOwnersLine(1, "/specific/dir/ @team", LineType.RULE, pattern="/specific/dir/", owners=["@team"]),
    ]
    matcher = CodeOwnersMatcher(rules)
    res = matcher.match_file("other/path.txt")
    assert not res.matched
    assert res.owners == []
    assert res.rule_line_number is None
