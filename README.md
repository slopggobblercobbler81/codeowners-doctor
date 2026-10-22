# codeowners-doctor

[![CI](https://github.com/slopggobblercobbler81/codeowners-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/codeowners-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**codeowners-doctor** is a production-grade CLI linter, ownership analyzer, pattern debugger, and formatter for GitHub, GitLab, and Bitbucket `CODEOWNERS` files.

---

## Why codeowners-doctor?

GitHub and GitLab silently ignore malformed `CODEOWNERS` syntax, leading to critical security and governance issues:
- **Shadowed Rules**: GitHub applies rules using **"last matching pattern wins"**. If an earlier specific rule is followed by a broader rule or catch-all `*`, the earlier rule is completely ignored.
- **Orphan Patterns**: Dead patterns matching files or directories that no longer exist in the repository.
- **Invalid Identifiers**: Typos in usernames, teams, or missing `@` prefixes mean intended reviewers are never requested on pull requests.
- **Unowned Gaps**: Critical files and newly introduced modules with zero code ownership coverage.
- **Duplicate Declarations**: Cluttered rules and duplicate owners across lines.

`codeowners-doctor` diagnoses all these issues, inspects ownership for any given file, audits repository coverage, and formats your file with clean column alignment.

---

## Features

- 🔍 **Comprehensive Linter & Diagnostics**: Detects syntax errors, missing owners, invalid GitHub usernames/teams/emails, duplicate owners, shadowed rules, and orphan patterns.
- 🎯 **Ownership Inspector (`who`)**: Accurately queries which rule and owners match any file path, strictly following platform precedence.
- 🛡️ **Coverage Audit (`unowned`)**: Scans repository files to detect untracked or unowned files without reviewer coverage.
- 🎨 **Smart Formatter (`format`)**: Aligns patterns and owners into clean columns, deduplicates owner names, and formats files cleanly in CI or via `--write`.
- ⚡ **Zero External Runtime Dependencies**: Standard library only, blazingly fast, runs everywhere.
- 🤖 **CI/CD Ready**: Supports `--format json` for automated reporting and `--strict` to fail builds on warnings.

---

## Installation

```bash
pip install codeowners-doctor
```

Or install locally in editable mode:

```bash
git clone https://github.com/slopggobblercobbler81/codeowners-doctor.git
cd codeowners-doctor
pip install -e .
```

---

## Quick Start

### 1. Lint and Diagnose

Auto-discovers `.github/CODEOWNERS`, `CODEOWNERS`, or `docs/CODEOWNERS`:

```bash
codeowners-doctor check
```

Run in strict mode for CI pipelines:

```bash
codeowners-doctor check --strict
```

Or output machine-readable JSON:

```bash
codeowners-doctor check --format json
```

### 2. Inspect File Ownership

Determine exactly which rule governs a file:

```bash
codeowners-doctor who src/components/Header.tsx
```

Output:
```text
File: src/components/Header.tsx
  Matched Rule: src/components/** (line 24)
  Owners:       @org/frontend-leads
```

### 3. Detect Unowned Files

Find any repository files currently lacking reviewer coverage:

```bash
codeowners-doctor unowned
```

### 4. Format & Align

Check if your `CODEOWNERS` file conforms to clean column formatting:

```bash
codeowners-doctor format --check
```

Automatically format and rewrite in place:

```bash
codeowners-doctor format --write
```

---

## Diagnostic Rules

| Code | Severity | Description |
|:-----|:---------|:------------|
| `E001` | **ERROR** | Syntax error in glob pattern or malformed rule |
| `E002` | **ERROR** | Rule pattern declared without any owners |
| `E003` | **ERROR** | Invalid owner format (must be `@user`, `@org/team`, or email) |
| `W001` | **WARNING** | Duplicate owner declared on the same rule line |
| `W002` | **WARNING** | Rule is completely shadowed or overridden by a subsequent rule |
| `W003` | **WARNING** | Orphan pattern matching 0 files in repository |
| `W004` | **WARNING** | Repository files detected with no matching code owners |
| `W005` | **WARNING** | Redundant wildcard pattern (e.g. leading `./` or `**/**`) |
| `W006` | **WARNING** | Multiple CODEOWNERS files exist (only the highest priority is used) |

---

## GitHub Actions CI Integration

Add `codeowners-doctor` to your GitHub Actions workflow:

```yaml
name: Lint CODEOWNERS

on:
  pull_request:
    paths:
      - '.github/CODEOWNERS'
      - 'CODEOWNERS'
      - 'docs/CODEOWNERS'

jobs:
  codeowners:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install codeowners-doctor
      - run: codeowners-doctor check --strict --unowned
```

---

## License

MIT License. Copyright (c) 2026 slopggobblercobbler81.
