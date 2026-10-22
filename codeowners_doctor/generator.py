"""Automatic CODEOWNERS template generator and starter builder."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Optional


STANDARD_ARCHETYPES = {
    "workflows": ("/.github/workflows/", "CI/CD & Automation workflows"),
    "security": ("/SECURITY.md", "Security disclosure policies & threat models"),
    "docker": ("Dockerfile", "Container build specifications"),
    "docs": ("/docs/", "Architecture & developer documentation"),
    "infra": ("/infra/", "Terraform & cloud infrastructure definitions"),
    "scripts": ("/scripts/", "Operational tooling & automation scripts"),
}


def generate_codeowners(
    default_owner: str = "@org/maintainers",
    sec_owner: Optional[str] = None,
    ops_owner: Optional[str] = None,
    docs_owner: Optional[str] = None,
    repo_dir: Optional[str | Path] = None,
) -> str:
    """Generate a clean, structured, and production-grade CODEOWNERS file.
    
    Inspects repo_dir (if provided) to detect existing architectural directories.
    """
    sec = sec_owner or default_owner
    ops = ops_owner or default_owner
    docs = docs_owner or default_owner

    lines = [
        "# ============================================================================",
        "# CODEOWNERS",
        "# See https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners",
        "# Generated with codeowners-doctor",
        "# ============================================================================",
        "",
        "# Global fallback: Everything in the repository unless overridden below",
        f"*                                       {default_owner}",
        "",
        "# CI/CD & Pipeline Configuration",
        f"/.github/workflows/                     {ops}",
        f"/.github/CODEOWNERS                     {default_owner}",
        "",
        "# Security Policies",
        f"/SECURITY.md                            {sec}",
        f"/security/                             {sec}",
        "",
        "# Infrastructure & Containerization",
        f"Dockerfile                              {ops}",
        f"docker-compose*.yml                     {ops}",
        "",
        "# Documentation & Guides",
        f"/docs/                                  {docs}",
        f"*.md                                    {docs}",
    ]

    # Auto-detect directories if repo_dir provided
    if repo_dir:
        rpath = Path(repo_dir)
        detected_sections: List[str] = []

        candidate_dirs = [
            ("src/", "@org/engineering", "Core source code"),
            ("apps/", "@org/engineering", "Microservices & applications"),
            ("packages/", "@org/engineering", "Shared libraries & monorepo packages"),
            ("frontend/", "@org/frontend-team", "Frontend user interface"),
            ("backend/", "@org/backend-team", "Backend services & API"),
            ("migrations/", "@org/db-admins", "Database schema migrations"),
            ("tests/", "@org/qa-team", "Automated test suites"),
            ("scripts/", ops, "Maintenance scripts & dev tooling"),
        ]

        for dirname, team, desc in candidate_dirs:
            if (rpath / dirname).is_dir():
                detected_sections.append(f"/{dirname:<39} {team}  # {desc}")

        if detected_sections:
            lines.append("")
            lines.append("# Detected Project Modules")
            lines.extend(detected_sections)

    lines.append("")
    return "\n".join(lines)
