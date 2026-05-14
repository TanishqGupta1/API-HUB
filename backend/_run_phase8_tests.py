"""Hermetic test runner for all Sinchana's Phase 8 / M1 backend work.

Covers (in order):
  - Task 6   payload_builder.py        (48 tests)
  - Task 7   preflight.py              (47 tests)
  - Task 2   constant-time ingest secret (2 tests)
  - Task 12  X-Orchestrator-Key auth   (4 tests)
  - Task 16  GET /push-requests/{id}   (5 tests)

Why this runner: the project conftest.py needs a live Postgres for its
autouse fixtures, which masks every hermetic test with an asyncpg error.
This runner imports test functions directly, skipping conftest, and
provides minimal shims for the few tests that use pytest fixtures
(`monkeypatch`).

Usage:
    cd backend && python _run_phase8_tests.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Required for SQLAlchemy engine init in some modules (lazy — doesn't connect).
os.environ.setdefault("POSTGRES_URL", "postgresql+asyncpg://x:x@localhost:5432/x")


# ────────────────────────────────────────────────────────────────────────
# Fixtures — minimal shims for pytest features we use
# ────────────────────────────────────────────────────────────────────────


class FakeMonkeypatch:
    """Stand-in for pytest's monkeypatch fixture. Tracks env var changes
    so we can restore on teardown."""

    def __init__(self):
        self._restore: list[tuple[str, str | None]] = []

    def setenv(self, name: str, value: str) -> None:
        self._restore.append((name, os.environ.get(name)))
        os.environ[name] = value

    def delenv(self, name: str, raising: bool = True) -> None:
        self._restore.append((name, os.environ.get(name)))
        os.environ.pop(name, None)

    def undo(self) -> None:
        for name, old in reversed(self._restore):
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old


def load_module(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ────────────────────────────────────────────────────────────────────────
# Test discovery + execution
# ────────────────────────────────────────────────────────────────────────


def discover_tests(mod):
    """Yield (name, callable, takes_monkeypatch_arg).

    Only inspects symbols actually defined in this module (skips imported
    helpers like FastAPI's `TestClient` that happen to start with `Test`).
    """
    mod_name = mod.__name__
    for name in sorted(dir(mod)):
        obj = getattr(mod, name)
        if callable(obj) and name.startswith("test_"):
            try:
                sig = inspect.signature(obj)
                yield name, obj, "monkeypatch" in sig.parameters
            except (ValueError, TypeError):
                yield name, obj, False
        elif isinstance(obj, type) and name.startswith("Test"):
            # Skip imported classes (e.g. fastapi.testclient.TestClient)
            if getattr(obj, "__module__", None) != mod_name:
                continue
            try:
                inst = obj()
            except TypeError:
                continue
            for method_name in sorted(dir(inst)):
                if method_name.startswith("test_"):
                    method = getattr(inst, method_name)
                    try:
                        sig = inspect.signature(method)
                        yield f"{name}::{method_name}", method, "monkeypatch" in sig.parameters
                    except (ValueError, TypeError):
                        yield f"{name}::{method_name}", method, False


def run_test_fn(fn, takes_monkeypatch: bool, app_fixture=None):
    """Invoke a test function with the right shims, awaiting if needed."""
    mp = FakeMonkeypatch()
    try:
        if app_fixture is not None:
            # T12 pattern — fixture takes monkeypatch, yields app
            app = app_fixture(mp)
            result = fn(app)
        elif takes_monkeypatch:
            result = fn(mp)
        else:
            result = fn()
        if inspect.iscoroutine(result):
            asyncio.run(result)
    finally:
        mp.undo()


def run_file(label: str, file_path: Path, app_fixture_name: str | None = None):
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    mod = load_module(file_path.stem, file_path)
    passed = failed = 0
    failures = []

    # If this test file has an `app` fixture (T12 pattern), grab its underlying fn
    app_fixture_fn = None
    if app_fixture_name:
        candidate = getattr(mod, app_fixture_name, None)
        if candidate:
            # pytest decorates fixtures — try unwrapping `__pytest_wrapped__` etc.
            app_fixture_fn = (
                getattr(candidate, "__wrapped__", None) or candidate.__pytest_wrapped__.obj
                if hasattr(candidate, "__pytest_wrapped__")
                else getattr(candidate, "__wrapped__", candidate)
            )

    for test_name, fn, takes_mp in discover_tests(mod):
        try:
            # Detect if the test takes an `app` arg (T12 pattern)
            sig = inspect.signature(fn)
            needs_app = "app" in sig.parameters and app_fixture_fn is not None
            run_test_fn(fn, takes_mp, app_fixture=app_fixture_fn if needs_app else None)
            print(f"  PASS  {test_name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test_name}: {type(exc).__name__}: {str(exc)[:200]}")
            failures.append((test_name, exc, traceback.format_exc()))
            failed += 1

    print(f"\n  Result: {passed} passed, {failed} failed (of {passed + failed})")
    return passed, failed, failures


# ────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────


def main():
    total_pass = total_fail = 0
    all_failures = []
    suites = [
        ("Task 6 — payload_builder.py", "tests/test_payload_builder.py", None),
        ("Task 7 — preflight.py", "tests/test_preflight.py", None),
        ("Task 2 — constant-time ingest secret", "tests/test_ingest_secret_constant_time.py", None),
        ("Task 12 — X-Orchestrator-Key auth", "tests/test_gateway_auth.py", "app"),
        ("Task 13 — Payload-hash idempotency ledger", "tests/test_gateway_idempotency.py", None),
        ("Task 16 — GET /push-requests/{id}", "tests/test_gateway_get_push_request.py", None),
        ("Task 20 — Collapse markup endpoints into /payload", "tests/test_markup_payload_collapse.py", None),
    ]
    for label, fname, app_fixture in suites:
        p, f, fails = run_file(label, ROOT / fname, app_fixture_name=app_fixture)
        total_pass += p
        total_fail += f
        all_failures.extend([(label, *t) for t in fails])

    print(f"\n{'=' * 70}")
    print(f"GRAND TOTAL: {total_pass} passed, {total_fail} failed (of {total_pass + total_fail})")
    print(f"{'=' * 70}")

    if all_failures:
        print("\n--- First 3 failures (full traceback) ---")
        for label, name, exc, tb in all_failures[:3]:
            print(f"\n[{label}] {name}")
            print(tb)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
