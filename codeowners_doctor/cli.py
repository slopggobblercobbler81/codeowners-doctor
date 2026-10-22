"""Command line interface for codeowners-doctor."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from codeowners_doctor import __version__
from codeowners_doctor.formatter import CodeOwnersFormatter
from codeowners_doctor.linter import CodeOwnersLinter, get_repository_files
from codeowners_doctor.matcher import CodeOwnersMatcher
from codeowners_doctor.models import DiagnosticSeverity
from codeowners_doctor.parser import CodeOwnersParser


# ANSI Colors with NO_COLOR and TTY check
def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


def _c(text: str, code: str) -> str:
    if not _use_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def red(text: str) -> str:
    return _c(text, "31;1")


def yellow(text: str) -> str:
    return _c(text, "33")


def green(text: str) -> str:
    return _c(text, "32;1")


def cyan(text: str) -> str:
    return _c(text, "36")


def bold(text: str) -> str:
    return _c(text, "1")


def dim(text: str) -> str:
    return _c(text, "2")


def _safe_symbol(char: str, fallback: str) -> str:
    try:
        char.encode(getattr(sys.stdout, "encoding", "utf-8") or "utf-8")
        return char
    except Exception:
        return fallback


CHECK_MARK = _safe_symbol("✓", "[OK]")
CROSS_MARK = _safe_symbol("✗", "[X]")
ARROW_MARK = _safe_symbol("↳", "->")


def resolve_codeowners_file(path_arg: Optional[str] = None, repo_root: Optional[Path] = None) -> Optional[Path]:
    """Finds the targeted CODEOWNERS file from arguments or discovery."""
    if path_arg:
        p = Path(path_arg)
        if p.is_file():
            return p.resolve()
        elif p.is_dir():
            candidates = CodeOwnersParser.discover_codeowners(p)
            if candidates:
                return candidates[0].resolve()
            return None

    root = repo_root or Path.cwd()
    candidates = CodeOwnersParser.discover_codeowners(root)
    if candidates:
        return candidates[0].resolve()

    return None


def cmd_check(args: argparse.Namespace) -> int:
    """Runs linting and validation on CODEOWNERS."""
    repo_root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    codeowners_path = resolve_codeowners_file(args.path, repo_root)

    if not codeowners_path or not codeowners_path.is_file():
        if args.format == "json":
            print(json.dumps({"error": "No CODEOWNERS file found", "diagnostics": []}, indent=2))
        else:
            print(red("Error: No CODEOWNERS file found."), file=sys.stderr)
            print("Checked locations: .github/CODEOWNERS, CODEOWNERS, docs/CODEOWNERS", file=sys.stderr)
        return 2

    # Discover candidate files in repo if repo_root wasn't specified but file is inside repo
    if not args.root:
        # If codeowners is in .github/CODEOWNERS, parent of .github is root
        parent = codeowners_path.parent
        if parent.name in (".github", "docs", ".gitlab"):
            repo_root = parent.parent
        else:
            repo_root = parent

    lines = CodeOwnersParser.parse_file(codeowners_path)
    linter = CodeOwnersLinter(lines, repo_root=repo_root, codeowners_path=codeowners_path)
    diagnostics = linter.run_all(check_unowned=args.unowned)

    # Check for multiple codeowners files
    all_codeowners = CodeOwnersParser.discover_codeowners(repo_root)
    if len(all_codeowners) > 1 and not args.path:
        from codeowners_doctor.models import Diagnostic
        other_files = [p.relative_to(repo_root).as_posix() for p in all_codeowners[1:]]
        diagnostics.append(
            Diagnostic(
                code="W006",
                message=(
                    f"Multiple CODEOWNERS files found. '{all_codeowners[0].relative_to(repo_root).as_posix()}' "
                    f"takes precedence. Ignored: {', '.join(other_files)}"
                ),
                severity=DiagnosticSeverity.WARNING,
                suggestion="Consolidate code owners into a single file.",
            )
        )

    has_errors = any(d.severity == DiagnosticSeverity.ERROR for d in diagnostics)
    has_warnings = any(d.severity == DiagnosticSeverity.WARNING for d in diagnostics)

    if args.format == "json":
        output = {
            "file": str(codeowners_path),
            "root": str(repo_root),
            "rules_count": len([l for l in lines if l.line_type.value == "rule"]),
            "diagnostics": [d.to_dict() for d in diagnostics],
            "passed": not has_errors and not (has_warnings and args.strict),
        }
        print(json.dumps(output, indent=2))
    else:
        rel_codeowners = codeowners_path
        try:
            rel_codeowners = codeowners_path.relative_to(repo_root)
        except ValueError:
            pass

        print(bold(f"CODEOWNERS Doctor: Checking {cyan(str(rel_codeowners))}"))
        print(dim(f"Repository Root: {repo_root}\n"))

        if not diagnostics:
            print(green(f"{CHECK_MARK} All checks passed! No issues found."))
        else:
            for diag in diagnostics:
                prefix = red("ERROR") if diag.severity == DiagnosticSeverity.ERROR else yellow("WARN ")
                loc = f"line {diag.line_number}: " if diag.line_number else ""
                print(f"[{prefix}] [{cyan(diag.code)}] {bold(loc)}{diag.message}")
                if diag.rule_line:
                    print(f"        {dim(diag.rule_line.strip())}")
                if diag.suggestion:
                    print(f"        {ARROW_MARK} {dim('Suggestion: ' + diag.suggestion)}")
                print()

            err_count = sum(1 for d in diagnostics if d.severity == DiagnosticSeverity.ERROR)
            warn_count = sum(1 for d in diagnostics if d.severity == DiagnosticSeverity.WARNING)
            print(f"Summary: {red(str(err_count))} error(s), {yellow(str(warn_count))} warning(s)")

    if has_errors:
        return 1
    if has_warnings and args.strict:
        return 1
    return 0


def cmd_who(args: argparse.Namespace) -> int:
    """Finds which rule and code owners govern a given file path."""
    repo_root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    codeowners_path = resolve_codeowners_file(args.path, repo_root)

    if not codeowners_path or not codeowners_path.is_file():
        print(red("Error: No CODEOWNERS file found."), file=sys.stderr)
        return 2

    lines = CodeOwnersParser.parse_file(codeowners_path)
    matcher = CodeOwnersMatcher(lines)
    result = matcher.match_file(args.file)

    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.matched:
            owners_str = ", ".join(result.owners) if result.owners else "None (unowned)"
            sec_str = f" in section [{result.section}]" if result.section else ""
            print(bold(f"File: {cyan(result.file_path)}"))
            print(f"  Matched Rule: {green(result.pattern or '')}{sec_str} (line {result.rule_line_number})")
            print(f"  Owners:       {bold(owners_str)}")
        else:
            print(yellow(f"File: {result.file_path}"))
            print(red("  No CODEOWNERS rule matches this file (unowned)."))

    return 0 if result.matched else 1


def cmd_unowned(args: argparse.Namespace) -> int:
    """Finds all files in repository that have no code owner assigned."""
    repo_root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    codeowners_path = resolve_codeowners_file(args.path, repo_root)

    if not codeowners_path or not codeowners_path.is_file():
        print(red("Error: No CODEOWNERS file found."), file=sys.stderr)
        return 2

    lines = CodeOwnersParser.parse_file(codeowners_path)
    matcher = CodeOwnersMatcher(lines)
    files = get_repository_files(repo_root)

    unowned: List[str] = []
    for f in files:
        res = matcher.match_file(f)
        if not res.matched:
            unowned.append(f)

    if args.format == "json":
        output = {
            "total_files": len(files),
            "unowned_count": len(unowned),
            "unowned_files": unowned,
        }
        print(json.dumps(output, indent=2))
    else:
        print(bold(f"Checking unowned files in {cyan(str(repo_root))}..."))
        print(f"Total files analyzed: {len(files)}")
        if not unowned:
            print(green(f"{CHECK_MARK} 100% code ownership coverage! No unowned files."))
        else:
            print(yellow(f"Found {len(unowned)} unowned file(s):"))
            for u in unowned:
                print(f"  - {u}")

    return 1 if unowned else 0


def cmd_format(args: argparse.Namespace) -> int:
    """Formats a CODEOWNERS file."""
    repo_root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    codeowners_path = resolve_codeowners_file(args.path, repo_root)

    if not codeowners_path or not codeowners_path.is_file():
        print(red("Error: No CODEOWNERS file found."), file=sys.stderr)
        return 2

    content = codeowners_path.read_text(encoding="utf-8")
    is_formatted, formatted = CodeOwnersFormatter.check_text(content)

    if args.check:
        if is_formatted:
            print(green(f"{CHECK_MARK} {codeowners_path.name} is properly formatted."))
            return 0
        else:
            print(yellow(f"{CROSS_MARK} {codeowners_path.name} is not formatted."))
            return 1

    if args.write:
        if not is_formatted:
            codeowners_path.write_text(formatted, encoding="utf-8")
            print(green(f"{CHECK_MARK} Formatted and updated {codeowners_path}."))
        else:
            print(dim(f"{codeowners_path.name} already well-formatted. No changes."))
        return 0

    # Default to stdout
    print(formatted, end="")
    return 0


def cmd_locate(args: argparse.Namespace) -> int:
    """Locates CODEOWNERS files in the repository and displays priority order."""
    repo_root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    found = CodeOwnersParser.discover_codeowners(repo_root)

    if args.format == "json":
        output = {
            "root": str(repo_root),
            "found": [str(p) for p in found],
            "active": str(found[0]) if found else None,
        }
        print(json.dumps(output, indent=2))
    else:
        print(bold(f"CODEOWNERS Discovery for {cyan(str(repo_root))}:"))
        if not found:
            print(yellow("No CODEOWNERS file found in standard locations."))
            print("Standard locations: .github/CODEOWNERS, CODEOWNERS, docs/CODEOWNERS")
        else:
            print(green(f"Active: {found[0].relative_to(repo_root).as_posix()}"))
            if len(found) > 1:
                print(yellow("Ignored duplicates (lower priority):"))
                for p in found[1:]:
                    print(f"  - {p.relative_to(repo_root).as_posix()}")

    return 0 if found else 1


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="codeowners-doctor",
        description="Production-grade CODEOWNERS validator, linter, analyzer, and formatter.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # check
    p_check = subparsers.add_parser("check", help="Lint and validate CODEOWNERS rules")
    p_check.add_argument("path", nargs="?", help="Path to CODEOWNERS file or repository")
    p_check.add_argument("-r", "--root", help="Repository root directory")
    p_check.add_argument("-s", "--strict", action="store_true", help="Fail with exit 1 on warnings")
    p_check.add_argument("-u", "--unowned", action="store_true", help="Also check for unowned files")
    p_check.add_argument("-f", "--format", choices=["text", "json"], default="text", help="Output format")

    # who
    p_who = subparsers.add_parser("who", help="Identify code owners for a specific file")
    p_who.add_argument("file", help="File path to test ownership for")
    p_who.add_argument("-p", "--path", help="Path to CODEOWNERS file")
    p_who.add_argument("-r", "--root", help="Repository root directory")
    p_who.add_argument("-f", "--format", choices=["text", "json"], default="text", help="Output format")

    # unowned
    p_unowned = subparsers.add_parser("unowned", help="List all unowned files in repository")
    p_unowned.add_argument("-p", "--path", help="Path to CODEOWNERS file")
    p_unowned.add_argument("-r", "--root", help="Repository root directory")
    p_unowned.add_argument("-f", "--format", choices=["text", "json"], default="text", help="Output format")

    # format
    p_fmt = subparsers.add_parser("format", help="Format CODEOWNERS file alignment and clean duplicates")
    p_fmt.add_argument("path", nargs="?", help="Path to CODEOWNERS file")
    p_fmt.add_argument("-r", "--root", help="Repository root directory")
    p_fmt.add_argument("-w", "--write", action="store_true", help="Format in place")
    p_fmt.add_argument("-c", "--check", action="store_true", help="Check formatting without writing")

    # locate
    p_locate = subparsers.add_parser("locate", help="Locate CODEOWNERS files and show precedence")
    p_locate.add_argument("-r", "--root", help="Repository root directory")
    p_locate.add_argument("-f", "--format", choices=["text", "json"], default="text", help="Output format")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        # Default behavior: run check
        args.command = "check"
        args.path = None
        args.root = None
        args.strict = False
        args.unowned = False
        args.format = "text"

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "who":
        return cmd_who(args)
    elif args.command == "unowned":
        return cmd_unowned(args)
    elif args.command == "format":
        return cmd_format(args)
    elif args.command == "locate":
        return cmd_locate(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
