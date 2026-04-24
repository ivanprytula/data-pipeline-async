#!/usr/bin/env python3
"""Phase 1 guardrails for service boundary enforcement.

Checks implemented:
1. No cross-service Python imports between the five service boundaries.
2. No direct access to another service's persistence modules
   (database/models/crud/storage/repository/repositories).

The five service boundaries are:
- ingestor
- services/ai_gateway
- services/query_api
- services/processor
- services/dashboard
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

SERVICE_ROOTS: dict[str, Path] = {
    "ingestor": REPO_ROOT / "ingestor",
    "ai_gateway": REPO_ROOT / "services" / "ai_gateway",
    "query_api": REPO_ROOT / "services" / "query_api",
    "processor": REPO_ROOT / "services" / "processor",
    "dashboard": REPO_ROOT / "services" / "dashboard",
}

PERSISTENCE_MODULE_HINTS = {
    "database",
    "models",
    "crud",
    "storage",
    "repository",
    "repositories",
}


@dataclass
class Violation:
    file: Path
    line: int
    code: str
    message: str


def detect_service_owner(file_path: Path) -> str | None:
    for service, root in SERVICE_ROOTS.items():
        try:
            file_path.relative_to(root)
            return service
        except ValueError:
            continue
    return None


def module_to_service(module: str) -> str | None:
    if module == "ingestor" or module.startswith("ingestor."):
        return "ingestor"

    if module == "services" or module.startswith("services."):
        parts = module.split(".")
        if len(parts) >= 2:
            svc = parts[1]
            if svc in {"ai_gateway", "query_api", "processor", "dashboard"}:
                return svc
    return None


def references_persistence_module(module: str) -> bool:
    return any(part in PERSISTENCE_MODULE_HINTS for part in module.split("."))


def extract_import_modules(node: ast.AST) -> list[tuple[int, str]]:
    modules: list[tuple[int, str]] = []

    if isinstance(node, ast.Import):
        for alias in node.names:
            modules.append((node.lineno, alias.name))

    if isinstance(node, ast.ImportFrom):
        if node.level and node.level > 0:
            return modules
        if node.module:
            modules.append((node.lineno, node.module))

    return modules


def scan_file(file_path: Path) -> list[Violation]:
    service_owner = detect_service_owner(file_path)
    if service_owner is None:
        return []

    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))

    violations: list[Violation] = []

    for node in ast.walk(tree):
        for line, module in extract_import_modules(node):
            target_service = module_to_service(module)
            if not target_service:
                continue

            if target_service != service_owner:
                violations.append(
                    Violation(
                        file=file_path,
                        line=line,
                        code="SVC001",
                        message=(
                            f"Cross-service import is forbidden: '{module}' "
                            f"from service '{service_owner}' to '{target_service}'."
                        ),
                    )
                )

            if target_service != service_owner and references_persistence_module(
                module
            ):
                violations.append(
                    Violation(
                        file=file_path,
                        line=line,
                        code="SVC002",
                        message=(
                            "Direct access to another service's persistence boundary is forbidden: "
                            f"'{module}'."
                        ),
                    )
                )

    return violations


def collect_service_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SERVICE_ROOTS.values():
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(files)


def main() -> int:
    files = collect_service_python_files()
    violations: list[Violation] = []

    for file_path in files:
        violations.extend(scan_file(file_path))

    if not violations:
        print("Service boundary guardrails passed (phase 1).")
        return 0

    print("Service boundary guardrails failed:")
    for violation in violations:
        rel_path = violation.file.relative_to(REPO_ROOT)
        print(f"- {rel_path}:{violation.line} [{violation.code}] {violation.message}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
