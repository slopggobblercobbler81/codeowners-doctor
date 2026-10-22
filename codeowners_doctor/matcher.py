"""Pattern matching engine for CODEOWNERS files."""

from __future__ import annotations
import os
import re
from typing import List, Optional, Tuple, Pattern
from .parser import CodeownersRule, ParsedCodeowners


def normalize_repo_path(path: str) -> str:
    """Normalize file path to unix-style relative path without leading ./ or /."""
    p = path.replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    if p.startswith("/"):
        p = p[1:]
    return p


def pattern_to_regex(pattern: str) -> Pattern[str]:
    """Convert a CODEOWNERS pattern into a compiled regex pattern.
    
    GitHub CODEOWNERS glob matching semantics:
    - Leading slash (/foo) anchors pattern to root of repo.
    - Pattern containing slash in middle (foo/bar) is also anchored to root.
    - Pattern without slash (or only trailing slash) matches at any directory depth.
    - Pattern ending with / matches directory and all its contents recursively.
    - Asterisk (*) matches zero or more non-slash characters.
    - Double asterisk (**) matches zero or more characters including slashes.
    """
    raw = pattern.strip()
    if not raw:
        return re.compile(r"^$")

    # Special case: '*' matches everything in repo
    if raw == "*":
        return re.compile(r"^.*$")

    is_dir_only = raw.endswith("/")
    if is_dir_only:
        raw = raw[:-1]

    # Check anchoring:
    # Starts with '/' -> anchored
    # Contains '/' -> anchored
    # Neither -> unanchored (matches anywhere)
    is_anchored = False
    if raw.startswith("/"):
        is_anchored = True
        raw = raw[1:]
    elif "/" in raw:
        is_anchored = True

    # Translate glob tokens into regex
    regex_parts: List[str] = []
    i = 0
    n = len(raw)

    while i < n:
        c = raw[i]

        if c == "\\":
            if i + 1 < n:
                regex_parts.append(re.escape(raw[i + 1]))
                i += 2
            else:
                regex_parts.append(re.escape("\\"))
                i += 1
            continue

        if c == "*":
            if i + 1 < n and raw[i + 1] == "*":
                # Double asterisk
                i += 2
                if i < n and raw[i] == "/":
                    # **/ -> matches zero or more directories
                    regex_parts.append(r"(?:.*/)?")
                    i += 1
                else:
                    regex_parts.append(r".*")
            else:
                regex_parts.append(r"[^/]*")
                i += 1
            continue

        if c == "?":
            regex_parts.append(r"[^/]")
            i += 1
            continue

        if c == ".":
            regex_parts.append(r"\.")
            i += 1
            continue

        if c in ("+", "^", "$", "(", ")", "[", "]", "{", "}", "|"):
            regex_parts.append(re.escape(c))
            i += 1
            continue

        regex_parts.append(c)
        i += 1

    pattern_body = "".join(regex_parts)

    if is_dir_only:
        # Must match directory itself or any file under that directory
        if is_anchored:
            final_regex = rf"^{pattern_body}(?:/.*)?$"
        else:
            final_regex = rf"(?:^|.*/){pattern_body}(?:/.*)?$"
    else:
        # Match exact file/dir or if it is a directory, match its contents
        if is_anchored:
            final_regex = rf"^{pattern_body}(?:/.*)?$"
        else:
            final_regex = rf"(?:^|.*/){pattern_body}(?:/.*)?$"

    return re.compile(final_regex)


class CodeownersMatcher:
    """Matches repository paths against CODEOWNERS rules using GitHub evaluation order."""

    def __init__(self, parsed_or_rules: ParsedCodeowners | List[CodeownersRule]) -> None:
        if isinstance(parsed_or_rules, ParsedCodeowners):
            self.rules = parsed_or_rules.rules
        else:
            self.rules = list(parsed_or_rules)

        self._compiled: List[Tuple[CodeownersRule, Pattern[str]]] = [
            (rule, pattern_to_regex(rule.pattern)) for rule in self.rules
        ]

    def find_all_matching_rules(self, path: str) -> List[CodeownersRule]:
        """Return all rules matching path in file order."""
        norm_path = normalize_repo_path(path)
        return [rule for rule, reg in self._compiled if reg.match(norm_path)]

    def find_matching_rule(self, path: str) -> Optional[CodeownersRule]:
        """Find the effective winning rule for path.
        
        In CODEOWNERS, rules are evaluated top-to-bottom and the LAST match wins.
        """
        norm_path = normalize_repo_path(path)
        for rule, reg in reversed(self._compiled):
            if reg.match(norm_path):
                return rule
        return None

    def get_owners(self, path: str) -> Tuple[str, ...]:
        """Get the owners tuple for path. Empty tuple if unowned or unmatched."""
        rule = self.find_matching_rule(path)
        if rule is None:
            return ()
        return rule.owners

    def is_owned(self, path: str) -> bool:
        """Check if path has at least one owner assigned."""
        return len(self.get_owners(path)) > 0
