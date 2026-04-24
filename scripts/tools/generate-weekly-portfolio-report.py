#!/usr/bin/env python3
"""Generate a weekly portfolio report from git activity."""

from __future__ import annotations

import argparse
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "docs/templates/weekly-portfolio-report-template.md"
DEFAULT_OUTPUT_DIR = ROOT / "docs/progress"


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def collect_commits(since_days: int) -> list[str]:
    output = run_git(
        "log",
        f"--since={since_days} days ago",
        "--pretty=format:- %h %ad %s",
        "--date=short",
    )
    return [line for line in output.splitlines() if line.strip()]


def collect_changed_files(since_days: int) -> list[str]:
    output = run_git(
        "log",
        f"--since={since_days} days ago",
        "--name-only",
        "--pretty=format:",
    )
    files = [line.strip() for line in output.splitlines() if line.strip()]
    return files


def top_paths(files: list[str], limit: int = 8) -> list[str]:
    counts = Counter(files)
    lines = []
    for path, count in counts.most_common(limit):
        lines.append(f"- {path} ({count} touches)")
    return lines


def resolve_week_label(explicit_label: str | None) -> str:
    if explicit_label:
        return explicit_label
    today = date.today().isoformat()
    return f"Week ending {today}"


def render_report(
    template: str,
    week_label: str,
    since_days: int,
    commits: list[str],
    changed_paths: list[str],
) -> str:
    commit_block = (
        "\n".join(commits) if commits else "- No commits found in selected window"
    )
    path_block = (
        "\n".join(changed_paths) if changed_paths else "- No changed files found"
    )

    return (
        template.replace("{{WEEK_LABEL}}", week_label)
        .replace("{{DATE}}", date.today().isoformat())
        .replace("{{SINCE_DAYS}}", str(since_days))
        .replace("{{COMMIT_SUMMARY}}", commit_block)
        .replace("{{TOP_CHANGED_PATHS}}", path_block)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--week-label", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"Template not found: {TEMPLATE_PATH}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    commits = collect_commits(args.since_days)
    files = collect_changed_files(args.since_days)
    changed = top_paths(files)

    week_label = resolve_week_label(args.week_label)
    rendered = render_report(template, week_label, args.since_days, commits, changed)

    output_path = args.output
    if output_path is None:
        output_name = f"weekly-progress-{date.today().isoformat()}.md"
        output_path = DEFAULT_OUTPUT_DIR / output_name

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Generated report: {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
