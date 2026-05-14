"""Hermetic test runner for Phase 8 M1 unit tests.

Imports test functions directly, skipping the project conftest.py
(which requires Postgres). The tests themselves don't touch DB.
"""
import asyncio
import inspect
import sys
import traceback
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def load_module(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_tests(mod):
    """Yield (name, callable) for every test function or class method."""
    for name in sorted(dir(mod)):
        obj = getattr(mod, name)
        if callable(obj) and name.startswith("test_"):
            yield name, obj
        elif isinstance(obj, type) and name.startswith("Test"):
            inst = obj()
            for method_name in sorted(dir(inst)):
                if method_name.startswith("test_"):
                    yield f"{name}::{method_name}", getattr(inst, method_name)


def run_file(label: str, file_path: Path):
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    mod = load_module(file_path.stem, file_path)
    passed = failed = 0
    failures = []
    for test_name, fn in discover_tests(mod):
        try:
            result = fn()
            if inspect.iscoroutine(result):
                asyncio.run(result)
            print(f"  PASS  {test_name}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {test_name}: {type(exc).__name__}: {exc}")
            failures.append((test_name, exc, traceback.format_exc()))
            failed += 1
    print(f"\n  Result: {passed} passed, {failed} failed (of {passed + failed})")
    return passed, failed, failures


total_pass = total_fail = 0
all_failures = []
for label, fname in [
    ("payload_builder.py", "tests/test_payload_builder.py"),
    ("preflight.py",       "tests/test_preflight.py"),
]:
    p, f, fails = run_file(label, ROOT / fname)
    total_pass += p
    total_fail += f
    all_failures.extend([(label, *t) for t in fails])

print(f"\n{'=' * 70}")
print(f"GRAND TOTAL: {total_pass} passed, {total_fail} failed (of {total_pass + total_fail})")
print(f"{'=' * 70}")

if all_failures:
    print("\n--- Failures (first 5) ---")
    for label, name, exc, tb in all_failures[:5]:
        print(f"\n[{label}] {name}")
        print(tb)
    sys.exit(1)
sys.exit(0)
