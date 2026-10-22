"""Pattern matching engine for CODEOWNERS."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from codeowners_doctor.models import CodeOwnersLine, LineType, MatchResult


def compile_pattern_to_regex(raw_pattern: str) -> re.Pattern:
    """Compiles a CODEOWNERS glob pattern into a compiled regex.
    
    Rules according to GitHub / git CODEOWNERS spec:
    - '*' alone matches all files across all directories.
    - '/*' matches only top-level files in the repo root.
    - Patterns starting with '/' are anchored to the repo root.
    - Patterns with a slash in the middle (not just trailing) are anchored to repo root.
    - Patterns ending in '/' match that directory and all files within it recursively.
    - Patterns without any slash match anywhere in the tree.
    - '**' matches zero or more directories.
    """
    pattern = raw_pattern.strip()

    # Universal wildcard
    if pattern == "*":
        return re.compile(r"^.*$")

    # Root files only
    if pattern == "/*":
        return re.compile(r"^[^/]+$")

    anchored_to_root = False
    if pattern.startswith("/"):
        anchored_to_root = True
        pattern = pattern[1:]

    matches_directory_recursively = False
    if pattern.endswith("/"):
        matches_directory_recursively = True
        pattern = pattern[:-1]

    # Check for slash in the middle
    if "/" in pattern:
        # If it has a slash in the middle (and didn't start with **/), it's anchored to root
        if not pattern.startswith("**/"):
            anchored_to_root = True

    # Build regex from glob pattern tokens
    regex_parts: List[str] = []
    i = 0
    n = len(pattern)

    while i < n:
        c = pattern[i]

        if c == "\\":
            if i + 1 < n:
                regex_parts.append(re.escape(pattern[i + 1]))
                i += 2
                continue
            else:
                regex_parts.append(re.escape(c))
                i += 1
                continue

        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # Double asterisk '**'
                # Check surrounding slashes
                # e.g., '**/', '/**', '/**/'
                prev_slash = i > 0 and pattern[i - 1] == "/"
                next_slash = i + 2 < n and pattern[i + 2] == "/"

                if prev_slash and next_slash:
                    # 'foo/**/bar' -> foo/(?:.+/)?bar
                    regex_parts.append(r"(?:.+/)?")
                    i += 3
                    continue
                elif next_slash:
                    # '**/bar' -> (?:.*/)?bar
                    regex_parts.append(r"(?:.*/)?")
                    i += 3
                    continue
                elif prev_slash:
                    # 'foo/**' -> foo/.*
                    regex_parts.append(r".*")
                    i += 2
                    continue
                else:
                    regex_parts.append(r".*")
                    i += 2
                    continue
            else:
                # Single asterisk '*' matches anything except '/'
                regex_parts.append(r"[^/]*")
                i += 1
                continue

        if c == "?":
            regex_parts.append(r"[^/]")
            i += 1
            continue

        if c == "[":
            # Character class
            j = i + 1
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j < n:
                char_class = pattern[i : j + 1]
                # convert [!abc] to [^abc]
                if char_class.startswith("[!"):
                    char_class = "[^" + char_class[2:]
                regex_parts.append(char_class)
                i = j + 1
                continue

        # Regular characters
        regex_parts.append(re.escape(c))
        i += 1

    pattern_body = "".join(regex_parts)

    if matches_directory_recursively:
        # Directory pattern: matches files directly in or inside subdirectories
        if anchored_to_root:
            regex_str = rf"^{pattern_body}(?:/.*)?$"
        else:
            regex_str = rf"^(?:.*/)?{pattern_body}(?:/.*)?$"
    else:
        # File or directory pattern:
        # If it's anchored to root:
        if anchored_to_root:
            regex_str = rf"^{pattern_body}(?:/.*)?$"
        else:
            # Can match anywhere in the hierarchy, or matches a directory whose contents match
            regex_str = rf"^(?:.*/)?{pattern_body}(?:/.*)?$"

    return re.compile(regex_str)


class CodeOwnersMatcher:
    """Matches files against parsed CODEOWNERS rules using GitHub precedence."""

    def __init__(self, rules: List[CodeOwnersLine]):
        self.raw_rules = rules
        self.compiled_rules: List[Tuple[CodeOwnersLine, re.Pattern]] = []

        for rule in rules:
            if rule.line_type == LineType.RULE and rule.pattern:
                try:
                    regex = compile_pattern_to_regex(rule.pattern)
                    self.compiled_rules.append((rule, regex))
                except re.error:
                    # Malformed regex pattern will be flagged by linter
                    pass

    @staticmethod
    def normalize_path(path_str: str) -> str:
        """Converts Windows or POSIX path to normalized repo-relative POSIX path."""
        p = path_str.replace("\\", "/").strip()
        while p.startswith("/"):
            p = p[1:]
        return p

    def match_file(self, file_path: str) -> MatchResult:
        """Finds the winning CODEOWNERS rule for a single file.
        
        According to GitHub spec, the last matching rule in the file wins.
        """
        norm_path = self.normalize_path(file_path)

        winning_rule: Optional[CodeOwnersLine] = None

        # Last matching pattern takes precedence
        for rule, regex in self.compiled_rules:
            if regex.match(norm_path):
                winning_rule = rule

        if winning_rule:
            return MatchResult(
                file_path=norm_path,
                matched=True,
                rule_line_number=winning_rule.line_number,
                pattern=winning_rule.pattern,
                owners=winning_rule.owners,
                section=winning_rule.section,
            )

        return MatchResult(
            file_path=norm_path,
            matched=False,
            rule_line_number=None,
            pattern=None,
            owners=[],
            section=None,
        )

    def match_all(self, file_paths: List[str]) -> Dict[str, MatchResult]:
        """Matches a list of file paths and returns results mapped by file path."""
        return {fp: self.match_file(fp) for fp in file_paths}
