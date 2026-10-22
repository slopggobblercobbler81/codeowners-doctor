"""Command Line Interface for codeowners-doctor."""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .parser import parse_codeowners
from .matcher import CodeownersMatcher
from .linter import CodeownersLinter, IssueSeverity
from .formatter import format_codeowners
from .audit import audit_ownership
from .generator import generate_codeowners


POSSIBLE_CODEOWNERS_PATHS = [
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
    ".gitlab/CODEOWNERS",
]


def find_codeowners_file(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Auto-detect CODEOWNERS file location in standard directories."""
    base = start_dir or Path.cwd()
    for rel in POSSIBLE_CODEOWNERS_PATHS:
        candidate = base / rel
        if candidate.is_file():
            return candidate
    return None


def _print_colored(text: str, color: str = "") -> None:
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    # Safely print with fallback for Windows non-UTF8 consoles
    try:
        if sys.stdout.isatty():
            sys.stdout.write(f"{colors.get(color, '')}{text}{colors['reset']}\n")
        else:
            sys.stdout.write(f"{text}\n")
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        fallback = text.encode(encoding, errors="replace").decode(encoding)
        sys.stdout.write(f"{fallback}\n")


def cmd_check(args: argparse.Namespace) -> int:
    """Execute 'check' linter command."""
    target_file = Path(args.file) if args.file else find_codeowners_file()
    if not target_file or not target_file.is_file():
        sys.stderr.write(
            f"Error: Could not locate CODEOWNERS file. Specify path with --file or run inside a git repository.\n"
        )
        return 1

    content = target_file.read_text(encoding="utf-8")
    repo_dir = Path(args.repo) if args.repo else target_file.parent.parent

    linter = CodeownersLinter(
        repo_dir=repo_dir if repo_dir.is_dir() else None,
        check_dead_rules=not args.no_dead_rules,
        check_critical_paths=not args.no_critical_check,
    )
    report = linter.lint(content)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.sarif:
        print(json.dumps(report.to_sarif(), indent=2))
    else:
        print(f"Scanning CODEOWNERS file: {target_file}")
        print(f"Found {report.total_rules} rules across {report.total_lines} lines.\n")

        if report.is_clean:
            _print_colored("[OK] No issues found! CODEOWNERS is healthy.", "green")
        else:
            for issue in report.issues:
                prefix = {
                    IssueSeverity.ERROR: "[ERROR]",
                    IssueSeverity.WARNING: "[WARN ]",
                    IssueSeverity.INFO: "[INFO ]",
                }[issue.severity]

                color = {
                    IssueSeverity.ERROR: "red",
                    IssueSeverity.WARNING: "yellow",
                    IssueSeverity.INFO: "blue",
                }[issue.severity]

                loc = f"Line {issue.line_number}: " if issue.line_number else ""
                _print_colored(f"{prefix} {loc}{issue.message}", color)
                if issue.suggestion:
                    print(f"       Suggestion: {issue.suggestion}")

            print(
                f"\nSummary: {len(report.errors)} error(s), {len(report.warnings)} warning(s), {len(report.infos)} info."
            )

    if report.has_errors:
        return 1
    if args.strict and len(report.warnings) > 0:
        return 1
    return 0


def cmd_who(args: argparse.Namespace) -> int:
    """Execute 'who' query command."""
    target_file = Path(args.file) if args.file else find_codeowners_file()
    if not target_file or not target_file.is_file():
        sys.stderr.write("Error: Could not locate CODEOWNERS file.\n")
        return 1

    content = target_file.read_text(encoding="utf-8")
    parsed = parse_codeowners(content)
    matcher = CodeownersMatcher(parsed)

    query_path = args.path
    rule = matcher.find_matching_rule(query_path)

    if args.json:
        result = {
            "path": query_path,
            "owned": bool(rule and rule.owners),
            "owners": list(rule.owners) if rule else [],
            "matching_rule": {
                "pattern": rule.pattern,
                "line_number": rule.line_number,
                "section": rule.section,
            } if rule else None,
        }
        print(json.dumps(result, indent=2))
    else:
        if rule and rule.owners:
            _print_colored(f"Path: {query_path}", "bold")
            _print_colored(f"Owners: {', '.join(rule.owners)}", "green")
            print(f"Matched Rule: '{rule.pattern}' (line {rule.line_number})")
            if rule.section:
                print(f"Section: {rule.section}")
        elif rule and not rule.owners:
            _print_colored(f"Path: {query_path}", "bold")
            _print_colored("Explicitly unowned (owners cleared by rule)", "yellow")
            print(f"Matched Rule: '{rule.pattern}' (line {rule.line_number})")
        else:
            _print_colored(f"Path: {query_path}", "bold")
            _print_colored("Unowned (no matching rule)", "red")

    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Execute 'audit' coverage report command."""
    target_file = Path(args.file) if args.file else find_codeowners_file()
    if not target_file or not target_file.is_file():
        sys.stderr.write("Error: Could not locate CODEOWNERS file.\n")
        return 1

    content = target_file.read_text(encoding="utf-8")
    repo_dir = Path(args.repo) if args.repo else target_file.parent.parent

    report = audit_ownership(content, repo_dir=repo_dir)

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    elif args.format == "markdown":
        print(report.to_markdown())
    else:
        print(report.to_text())

    if args.min_coverage is not None and report.coverage_percent < args.min_coverage:
        sys.stderr.write(
            f"\nCoverage check failed: {report.coverage_percent:.1f}% < minimum threshold {args.min_coverage}%\n"
        )
        return 1

    return 0


def cmd_format(args: argparse.Namespace) -> int:
    """Execute 'format' or 'fix' command."""
    target_file = Path(args.file) if args.file else find_codeowners_file()
    if not target_file or not target_file.is_file():
        sys.stderr.write("Error: Could not locate CODEOWNERS file.\n")
        return 1

    content = target_file.read_text(encoding="utf-8")
    repo_dir = Path(args.repo) if args.repo else target_file.parent.parent

    repo_files: Optional[List[str]] = None
    if args.remove_dead and repo_dir.is_dir():
        from .linter import CodeownersLinter
        repo_files = CodeownersLinter(repo_dir=repo_dir)._discover_repo_files()

    formatted = format_codeowners(
        content=content,
        align_columns=not args.no_align,
        dedup_owners=True,
        repo_files=repo_files,
        remove_dead=args.remove_dead,
    )

    if args.in_place:
        target_file.write_text(formatted, encoding="utf-8")
        _print_colored(f"Formatted and saved: {target_file}", "green")
    elif args.output:
        Path(args.output).write_text(formatted, encoding="utf-8")
        _print_colored(f"Formatted and saved to: {args.output}", "green")
    else:
        sys.stdout.write(formatted)

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Execute 'init' template generator command."""
    out_path = Path(args.out) if args.out else Path(".github/CODEOWNERS")
    if out_path.exists() and not args.force:
        sys.stderr.write(f"Error: Destination {out_path} already exists. Use --force to overwrite.\n")
        return 1

    generated = generate_codeowners(
        default_owner=args.default_owner,
        sec_owner=args.security_owner,
        ops_owner=args.ops_owner,
        docs_owner=args.docs_owner,
        repo_dir=Path.cwd(),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(generated, encoding="utf-8")
    _print_colored(f"Successfully generated starter CODEOWNERS at {out_path}", "green")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="codeowners-doctor",
        description="Production-grade CODEOWNERS validator, ownership auditor, linter, and formatter.",
    )
    parser.add_argument("--version", action="version", version=f"codeowners-doctor {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # check command
    p_check = subparsers.add_parser("check", help="Lint and validate CODEOWNERS file (default)")
    p_check.add_argument("file", nargs="?", help="Path to CODEOWNERS file (auto-detected if omitted)")
    p_check.add_argument("--repo", help="Path to repository root")
    p_check.add_argument("--strict", action="store_true", help="Fail with exit 1 on warnings")
    p_check.add_argument("--no-dead-rules", action="store_true", help="Skip dead rule checks against repo files")
    p_check.add_argument("--no-critical-check", action="store_true", help="Skip critical security paths check")
    p_check.add_argument("--json", action="store_true", help="Output results as JSON")
    p_check.add_argument("--sarif", action="store_true", help="Output results as SARIF for GitHub Code Scanning")

    # who command
    p_who = subparsers.add_parser("who", help="Query which owner(s) are responsible for a file path")
    p_who.add_argument("path", help="Relative file or directory path to query")
    p_who.add_argument("--file", help="Path to CODEOWNERS file")
    p_who.add_argument("--json", action="store_true", help="Output as JSON")

    # audit command
    p_audit = subparsers.add_parser("audit", help="Audit ownership coverage across repository files")
    p_audit.add_argument("--file", help="Path to CODEOWNERS file")
    p_audit.add_argument("--repo", help="Path to repository root")
    p_audit.add_argument("--format", choices=["text", "markdown", "json"], default="text", help="Output format")
    p_audit.add_argument("--min-coverage", type=float, help="Fail if coverage percentage is below threshold")

    # format / fix command
    p_fmt = subparsers.add_parser("format", help="Reformat and tidy CODEOWNERS file")
    p_fmt.add_argument("--file", help="Path to CODEOWNERS file")
    p_fmt.add_argument("--repo", help="Path to repository root")
    p_fmt.add_argument("-i", "--in-place", action="store_true", help="Modify file in-place")
    p_fmt.add_argument("-o", "--output", help="Write formatted output to specified file")
    p_fmt.add_argument("--no-align", action="store_true", help="Disable column alignment")
    p_fmt.add_argument("--remove-dead", action="store_true", help="Strip patterns that match 0 files in repo")

    # alias fix -> format
    p_fix = subparsers.add_parser("fix", help="Alias for 'format --remove-dead -i'")
    p_fix.add_argument("--file", help="Path to CODEOWNERS file")
    p_fix.add_argument("--repo", help="Path to repository root")
    p_fix.add_argument("-i", "--in-place", action="store_true", default=True, help="Modify file in-place (default)")
    p_fix.add_argument("-o", "--output", help="Write formatted output to specified file")
    p_fix.add_argument("--no-align", action="store_true", help="Disable column alignment")
    p_fix.add_argument("--remove-dead", action="store_true", default=True, help="Strip patterns that match 0 files")

    # init command
    p_init = subparsers.add_parser("init", help="Generate production starter CODEOWNERS file")
    p_init.add_argument("--out", help="Output path (default: .github/CODEOWNERS)")
    p_init.add_argument("--default-owner", default="@org/maintainers", help="Default owner for wildcard rule")
    p_init.add_argument("--security-owner", help="Owner for security policies")
    p_init.add_argument("--ops-owner", help="Owner for CI/CD and infra")
    p_init.add_argument("--docs-owner", help="Owner for documentation")
    p_init.add_argument("-f", "--force", action="store_true", help="Overwrite if destination exists")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command or args.command == "check":
        if not args.command:
            # Default to check command
            args = parser.parse_args(["check"] + (argv or []))
        return cmd_check(args)
    elif args.command == "who":
        return cmd_who(args)
    elif args.command == "audit":
        return cmd_audit(args)
    elif args.command in ("format", "fix"):
        return cmd_format(args)
    elif args.command == "init":
        return cmd_init(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
