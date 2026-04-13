## Plan: Organize tests by domain and testing pyramid

TL;DR - Reorganize the `tests/` tree into `tests/unit/records`, `tests/integration/records`, and `tests/e2e/records`. Move existing tests into appropriate layers, add lightweight `conftest.py` fixtures per layer (reuse existing fixtures where appropriate), add pytest markers (`unit`, `integration`, `e2e`), and update CI/test commands. Keep tests behaviour unchanged; verify by running full test suite.

**Steps**
1. Discovery: identify current tests and categorize them (unit vs integration vs e2e).
   - *Depends on:* repository scan (done manually in plan: tests present: `test_logging.py`, `test_api.py`, `test_under_constraints.py`, `test_performance.py`).
2. Create directory layout under `tests/`:
   - `tests/unit/records/`
   - `tests/integration/records/`
   - `tests/e2e/records/`
   - Keep `tests/shared/` for common helpers/fixtures if useful.
3. Move tests into categories:
   - Unit:
     - `tests/test_logging.py` → `tests/unit/records/test_logging.py` (pure logic, no HTTP/DB)
     - Any other pure-unit tests (none currently)
   - Integration:
     - `tests/test_api.py` → `tests/integration/records/test_api.py` (uses ASGI client and DB via fixtures)
     - `tests/test_performance.py` (if it uses app internals / DB) → `tests/integration/records/test_performance.py`
   - E2E / long-running / constraints:
     - `tests/test_under_constraints.py` → `tests/e2e/records/test_under_constraints.py`
4. Consolidate fixtures:
   - Keep top-level `tests/conftest.py` for shared fixtures (`client`, DB session) used by integration and e2e tests.
   - Add `tests/unit/conftest.py` if unit tests require specific minimal fixtures (e.g., `monkeypatch` defaults) to keep isolation.
   - Add `tests/integration/conftest.py` only if integration layer needs overrides (e.g., DB lifecycle), otherwise reuse top-level.
5. Add pytest markers and config:
   - Add `pytest.ini` (or update `pyproject.toml` tests section) with markers:
     - `[pytest]
       markers =
         unit: Fast, isolated unit tests
         integration: Tests that touch DB/ASGI
         e2e: End-to-end or long-running tests
   - Optionally add `-k "not e2e"` default to CI to skip long tests; document commands in README.
6. Update CI/test commands in docs:
   - Examples:
     - Run unit tests: `pytest tests/unit -q`
     - Run integration: `pytest tests/integration -q`
     - Run e2e: `pytest tests/e2e -q -s`
     - Run all: `pytest -q`
7. Move files (implementation notes for whoever runs it):
   - Use `git mv` to preserve history when moving test files.
8. Verification:
   - Run `pytest -q` and ensure all tests pass after moving.
   - Run `pytest tests/unit -q` and `pytest tests/integration -q` separately to validate layering.
   - Confirm CI pipeline uses the proper commands (update if necessary).

**Relevant files**
- `tests/test_logging.py` — move to `tests/unit/records/test_logging.py`
- `tests/test_api.py` — move to `tests/integration/records/test_api.py`
- `tests/test_under_constraints.py` — move to `tests/e2e/records/test_under_constraints.py`
- `tests/conftest.py` — review and split if needed into `tests/unit/conftest.py` and `tests/integration/conftest.py`
- Add `pytest.ini` at project root (if not present)

**Verification**
1. Local: run `pytest -q` and confirm same result as before.
2. CI: update test commands to run `pytest -q` or the desired subset; ensure long-running tests are not run by default.
3. Sanity: open a few moved files and run a single test function via `pytest path::test_name -q` to ensure imports/fixtures work.

**Decisions / Assumptions**
- Integration tests are defined as tests using the ASGI client and touching DB; they remain in `tests/integration/`.
- E2E tests are long-running or resource-constrained tests; they remain excluded from CI by default.
- We will not change test logic, only move files and adjust fixtures/import paths if necessary.

**Further considerations**
1. Do you want `tests/shared/` for helpers (factories, sample payloads)? Recommended for reuse (e.g., `_RECORD` payload currently in `test_api.py`).
2. Do you want me to implement the moves and add `pytest.ini` now, or just provide a patch/PR you will run? Please confirm so I can proceed with implementation steps.