"""Unit tests for CODEOWNERS matcher."""

import pytest
from codeowners_doctor.parser import parse_codeowners
from codeowners_doctor.matcher import CodeownersMatcher, normalize_repo_path, pattern_to_regex


def test_normalize_repo_path():
    assert normalize_repo_path("./foo/bar.txt") == "foo/bar.txt"
    assert normalize_repo_path("/foo/bar.txt") == "foo/bar.txt"
    assert normalize_repo_path(r"foo\bar\baz.txt") == "foo/bar/baz.txt"
    assert normalize_repo_path("  file.txt  ") == "file.txt"


def test_matcher_wildcard_default():
    content = "* @default"
    matcher = CodeownersMatcher(parse_codeowners(content))

    assert matcher.get_owners("README.md") == ("@default",)
    assert matcher.get_owners("src/index.js") == ("@default",)
    assert matcher.get_owners("deep/nested/path/to/file.py") == ("@default",)


def test_matcher_order_precedence():
    content = """
* @everyone
*.js @js-team
/src/special.js @alice
"""
    matcher = CodeownersMatcher(parse_codeowners(content))

    # General file
    assert matcher.get_owners("README.md") == ("@everyone",)
    # JS file elsewhere
    assert matcher.get_owners("lib/util.js") == ("@js-team",)
    # Root js file
    assert matcher.get_owners("index.js") == ("@js-team",)
    # Most specific winning rule
    assert matcher.get_owners("src/special.js") == ("@alice",)


def test_matcher_anchored_vs_unanchored():
    content = """
/docs/ @root-docs
images/ @any-images
build/ @any-build
"""
    matcher = CodeownersMatcher(parse_codeowners(content))

    # /docs/ is anchored at root
    assert matcher.get_owners("docs/intro.md") == ("@root-docs",)
    assert matcher.get_owners("packages/app/docs/intro.md") == ()

    # images/ is unanchored (matches anywhere)
    assert matcher.get_owners("images/logo.png") == ("@any-images",)
    assert matcher.get_owners("assets/images/logo.png") == ("@any-images",)

    # build/
    assert matcher.get_owners("build/output.js") == ("@any-build",)
    assert matcher.get_owners("src/build/output.js") == ("@any-build",)


def test_matcher_unowned_rule():
    content = """
* @maintainers
/secrets/
"""
    matcher = CodeownersMatcher(parse_codeowners(content))

    assert matcher.get_owners("app.py") == ("@maintainers",)
    assert matcher.is_owned("app.py") is True

    # /secrets/ matches and explicitly clears ownership
    assert matcher.get_owners("secrets/keys.txt") == ()
    assert matcher.is_owned("secrets/keys.txt") is False


def test_matcher_double_asterisk():
    content = """
apps/**/tests/ @qa-team
"""
    matcher = CodeownersMatcher(parse_codeowners(content))

    assert matcher.get_owners("apps/api/tests/test_api.py") == ("@qa-team",)
    assert matcher.get_owners("apps/web/client/tests/test_client.py") == ("@qa-team",)
    assert matcher.get_owners("apps/api/src/server.py") == ()


def test_matcher_find_all_matching_rules():
    content = """
* @all
*.py @python-devs
/src/app.py @lead
"""
    matcher = CodeownersMatcher(parse_codeowners(content))
    matches = matcher.find_all_matching_rules("src/app.py")
    assert len(matches) == 3
    assert matches[0].pattern == "*"
    assert matches[1].pattern == "*.py"
    assert matches[2].pattern == "/src/app.py"

    # Effective rule is the last one
    assert matcher.find_matching_rule("src/app.py").pattern == "/src/app.py"


def test_matcher_direct_rules_list():
    from codeowners_doctor.parser import CodeownersRule
    rules = [
        CodeownersRule(pattern="*.rs", owners=("@rustacean",), line_number=1, raw_line="*.rs @rustacean"),
        CodeownersRule(pattern="README.md", owners=(), line_number=2, raw_line="README.md"),
    ]
    matcher = CodeownersMatcher(rules)
    assert matcher.get_owners("main.rs") == ("@rustacean",)
    assert matcher.is_owned("main.rs") is True
    assert matcher.get_owners("README.md") == ()
    assert matcher.is_owned("README.md") is False
    assert matcher.get_owners("unknown.txt") == ()
    assert matcher.find_matching_rule("unknown.txt") is None


def test_pattern_to_regex_special_cases():
    # Empty pattern
    assert pattern_to_regex("").pattern == "^$"

    # Escaped characters
    reg_space = pattern_to_regex(r"my\ file.txt")
    assert reg_space.match("my file.txt")

    # Question mark
    reg_q = pattern_to_regex("file?.txt")
    assert reg_q.match("file1.txt")
    assert not reg_q.match("file12.txt")
