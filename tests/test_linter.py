"""Unit tests for CODEOWNERS linter."""

import pytest
from codeowners_doctor.linter import CodeownersLinter, IssueSeverity, LintIssue


def test_clean_codeowners():
    content = """# Clean CODEOWNERS
* @org/team
/docs/ @docs-team
*.py dev@example.com
"""
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    assert report.is_clean
    assert len(report.issues) == 0
    assert not report.has_errors
    assert report.total_rules == 3


def test_trailing_whitespace_issue():
    content = "* @team   \n/docs/ @docs\t"
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    ws_issues = [i for i in report.issues if i.code == "TRAILING_WHITESPACE"]
    assert len(ws_issues) == 2
    assert ws_issues[0].line_number == 1
    assert ws_issues[1].line_number == 2


def test_invalid_owner_format():
    content = """
* valid-user-missing-at
*.js @valid-team
/src/ invalid@notanemail
"""
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    errs = [i for i in report.issues if i.code == "OWNER_FORMAT_INVALID"]
    assert len(errs) == 2
    assert report.has_errors


def test_duplicate_owner_on_rule():
    content = "*.py @alice @bob @alice"
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    dups = [i for i in report.issues if i.code == "DUPLICATE_OWNER"]
    assert len(dups) == 1
    assert "Duplicate owner '@alice'" in dups[0].message


def test_duplicate_identical_rules():
    content = """
/docs/ @docs-team
/docs/ @docs-team
"""
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    dups = [i for i in report.issues if i.code == "DUPLICATE_RULE"]
    assert len(dups) == 1
    assert dups[0].line_number == 3


def test_shadowed_rule_warning():
    content = """
/docs/ @alice
/src/ @bob
/docs/ @charlie
"""
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    shadowed = [i for i in report.issues if i.code == "SHADOWED_RULE"]
    assert len(shadowed) == 1
    assert shadowed[0].line_number == 2  # line 2 (/docs/ @alice) is shadowed by line 4


def test_dead_rule_detection():
    content = """
/exists.py @alice
/ghost.py @bob
"""
    files = ["exists.py", "readme.md"]
    linter = CodeownersLinter(files_list=files, check_dead_rules=True, check_critical_paths=False)
    report = linter.lint(content)

    dead = [i for i in report.issues if i.code == "DEAD_RULE"]
    assert len(dead) == 1
    assert dead[0].rule.pattern == "/ghost.py"


def test_critical_paths_unowned():
    content = """
/docs/ @docs-team
"""
    files = [".github/workflows/ci.yml", "docs/index.md"]
    linter = CodeownersLinter(files_list=files, check_dead_rules=False, check_critical_paths=True)
    report = linter.lint(content)

    crit = [i for i in report.issues if i.code == "UNOWNED_CRITICAL_PATH"]
    assert len(crit) == 1
    assert "ci.yml" in crit[0].message


def test_sarif_export():
    content = "*.py invalid_owner"
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    sarif = report.to_sarif()
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1
    assert len(sarif["runs"][0]["results"]) >= 1
    assert sarif["runs"][0]["results"][0]["ruleId"] == "OWNER_FORMAT_INVALID"


def test_backslash_in_pattern_and_missing_owners():
    content = r"""
src\\models\\file.py @team
/unowned/
"""
    linter = CodeownersLinter(check_dead_rules=False, check_critical_paths=False)
    report = linter.lint(content)

    bs = [i for i in report.issues if i.code == "BACKSLASH_IN_PATTERN"]
    assert len(bs) == 1
    assert "src/models/file.py" in bs[0].suggestion

    missing = [i for i in report.issues if i.code == "MISSING_OWNERS"]
    assert len(missing) == 1
    assert missing[0].severity == IssueSeverity.INFO

    # Check to_dict on issue
    d = bs[0].to_dict()
    assert d["code"] == "BACKSLASH_IN_PATTERN"
    assert d["severity"] == "warning"
