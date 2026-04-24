#!/usr/bin/env python3
"""Quality checks for Markdown docs used in CI."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

MD_GLOBS = (
    "README.md",
    "docs/**/*.md",
    ".github/prompts/**/*.md",
)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BOLD_HEADING_RE = re.compile(r"^\*\*[^*].*\*\*\s*$")
FENCE_RE = re.compile(r"^```([^\s`].*)?$")


def markdown_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in MD_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file():
                files.add(path)
    return sorted(files)


def is_external_link(target: str) -> bool:
    return (
        target.startswith("http://")
        or target.startswith("https://")
        or target.startswith("mailto:")
        or target.startswith("#")
    )


def normalize_target(base: Path, target: str) -> Path:
    no_anchor = target.split("#", 1)[0]
    return (base / no_anchor).resolve()


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    rel_path = path.relative_to(ROOT)

    in_fence = False
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")

        if BOLD_HEADING_RE.match(line):
            errors.append(
                f"{rel_path}:{line_no}: bold-only heading detected (use markdown headings)."
            )

        if line.startswith("```"):
            if not in_fence:
                if not FENCE_RE.match(line) or line.strip() == "```":
                    errors.append(
                        f"{rel_path}:{line_no}: fenced code block missing language tag."
                    )
                in_fence = True
            else:
                in_fence = False

        for match in LINK_RE.finditer(line):
            target = match.group(1).strip()
            if not target or is_external_link(target):
                continue
            if target.startswith("`"):
                continue

            resolved = normalize_target(path.parent, target)
            if not resolved.exists():
                errors.append(
                    f"{rel_path}:{line_no}: broken local link target '{target}'."
                )

    if in_fence:
        errors.append(f"{rel_path}: unclosed fenced code block.")

    return errors


def main() -> int:
    files = markdown_files()
    if not files:
        print("No markdown files found for docs quality check.")
        return 0

    all_errors: list[str] = []
    for file_path in files:
        all_errors.extend(check_file(file_path))

    if all_errors:
        print("Docs quality check failed:")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print(f"Docs quality check passed for {len(files)} markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
