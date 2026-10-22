# codeowners-doctor 🩺

[![CI](https://github.com/slopggobblercobbler81/codeowners-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/codeowners-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)

Production-grade **CODEOWNERS** validator, ownership auditor, linter, query tool, and auto-formatter designed for modern CI/CD pipelines and developer workflows.

---

## Why codeowners-doctor?

GitHub and GitLab `CODEOWNERS` files are critical for repository security, compliance, and code review governance. However, they frequently suffer from silent degradation:
- **Dead rules**: Patterns pointing to deleted or renamed paths that match zero files.
- **Shadowed rules**: Broad or duplicate rules overridden by earlier or later definitions.
- **Syntax & format errors**: Unescaped backslashes, missing `@` prefixes, or invalid email formats.
- **Coverage blindspots**: Security-sensitive paths (e.g. CI workflows, security policies, Dockerfiles) left without dedicated review ownership.
- **Inconsistent formatting**: Unaligned columns and chaotic rules that are hard to inspect.

`codeowners-doctor` diagnoses, reports, audits, and fixes all these issues with zero external dependencies.

---

## Features

- **🔍 Comprehensive Linter (`check`)**:
  - Detects dead patterns matching zero repo files.
  - Warns on shadowed rules and duplicate declarations.
  - Flags invalid usernames, team slugs, and email addresses.
  - Detects unescaped Windows backslashes (`\`) vs POSIX slashes (`/`).
  - Audits unowned critical security and CI paths (`.github/workflows`, `SECURITY.md`, `Dockerfile`, etc.).
  - Exports diagnostics in standard **SARIF 2.1.0** for GitHub Code Scanning alerts, or machine-readable JSON.

- **🎯 Ownership Query Engine (`who`)**:
  - Full adherence to GitHub/GitLab pattern-matching semantics (wildcards `*`, recursive directory traversal `**`, root anchoring, trailing slash directory matching).
  - Accurately resolves the winning owner rule and section for any queried file.

- **📊 Coverage & Ownership Audit (`audit`)**:
  - Calculates total repository ownership percentage.
  - Identifies every unowned file.
  - Computes ownership breakdown and distribution across teams and users.
  - Supports threshold enforcement via `--min-coverage <percentage>` for CI quality gates.
  - Exports reports in Text, Markdown (with collapsible details), and JSON.

- **✨ Automatic Formatter & Auto-Fixer (`format`, `fix`)**:
  - Neatly aligns patterns and owner columns.
  - Strips trailing whitespace and normalizes newlines.
  - Deduplicates identical owners per rule.
  - Prunes dead rules matching non-existent files with `--remove-dead`.
  - Supports `--in-place` (`-i`) updating.

- **🚀 Template Generator (`init`)**:
  - Generates robust starter `CODEOWNERS` with best-practice groupings (CI/CD, Security, Infrastructure, Documentation, Modules).

---

## Installation

Install via pip:

```bash
pip install codeowners-doctor
```

Or install from source:

```bash
git clone https://github.com/slopggobblercobbler81/codeowners-doctor.git
cd codeowners-doctor
pip install -e .
```

---

## CLI Usage

### 1. Validate & Lint CODEOWNERS

Auto-detects `.github/CODEOWNERS`, `CODEOWNERS`, or `docs/CODEOWNERS`:

```bash
# Basic check
codeowners-doctor check

# Strict mode: fail on warnings as well as errors
codeowners-doctor check --strict

# Specific file and repository root
codeowners-doctor check .github/CODEOWNERS --repo .

# Output as JSON or SARIF for GitHub Actions Code Scanning
codeowners-doctor check --json
codeowners-doctor check --sarif > results.sarif
```

### 2. Query Ownership of a File (`who`)

Find out which owner is responsible for any path in your repository:

```bash
codeowners-doctor who src/auth/jwt.py
codeowners-doctor who .github/workflows/deploy.yml --json
```

Output:
```text
Path: src/auth/jwt.py
Owners: @org/security-team, @alice
Matched Rule: '/src/auth/' (line 14)
```

### 3. Repository Ownership Audit (`audit`)

Measure ownership coverage across all files in your repository:

```bash
# Print summary to terminal
codeowners-doctor audit

# Enforce a minimum 90% ownership threshold in CI
codeowners-doctor audit --min-coverage 90.0

# Generate Markdown report for GitHub PR comments
codeowners-doctor audit --format markdown > ownership-report.md
```

### 4. Auto-Format and Clean Rules (`format` / `fix`)

Tidy up spacing, align columns, and optionally remove dead rules:

```bash
# In-place format with column alignment
codeowners-doctor format -i

# Strip dead patterns and auto-format
codeowners-doctor fix
```

### 5. Initialize a New CODEOWNERS File (`init`)

Generate a production-ready starter template:

```bash
codeowners-doctor init \
  --default-owner "@org/core-maintainers" \
  --security-owner "@org/sec-team" \
  --ops-owner "@org/devops"
```

---

## GitHub Actions CI Integration

Add `codeowners-doctor` to your GitHub Actions workflow:

```yaml
name: CODEOWNERS Health Check

on:
  pull_request:
    paths:
      - '.github/CODEOWNERS'
      - 'CODEOWNERS'
      - 'docs/CODEOWNERS'
  push:
    branches: [main]

jobs:
  codeowners-doctor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install codeowners-doctor
        run: pip install codeowners-doctor

      - name: Lint CODEOWNERS
        run: codeowners-doctor check --strict

      - name: Enforce Minimum Ownership Coverage
        run: codeowners-doctor audit --min-coverage 85.0
```

---

## Python API Usage

`codeowners-doctor` can also be used as a standalone Python library:

```python
from codeowners_doctor import (
    parse_codeowners,
    CodeownersMatcher,
    CodeownersLinter,
    audit_ownership,
    format_codeowners,
)

content = """
* @org/team
/docs/ @docs-team
"""

# Parsing
parsed = parse_codeowners(content)
for rule in parsed.rules:
    print(rule.pattern, rule.owners)

# Matching
matcher = CodeownersMatcher(parsed)
owners = matcher.get_owners("docs/index.md")  # ('@docs-team',)

# Linting
linter = CodeownersLinter()
report = linter.lint(content)
print(f"Is healthy: {report.is_clean}")

# Coverage Audit
audit = audit_ownership(parsed, files_list=["README.md", "docs/index.md"])
print(f"Coverage: {audit.coverage_percent}%")
```

---

## Development & Testing

Run tests with `pytest`:

```bash
pip install -e ".[dev]"
pytest -v --cov=codeowners_doctor
```

---

## License

This project is licensed under the [MIT License](LICENSE).
