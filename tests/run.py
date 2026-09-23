"""Run every test in every test module.

Each test file used to run itself from an `if __name__ == "__main__"` block at
the bottom. Appending a test after that block defines it *after* the runner has
already executed, so it never runs and the file still reports success -- which
had quietly disabled 14 of 71 tests, including four of the sovereignty checks.

Importing the modules and collecting their functions afterwards cannot skip a
test by position.

    .venv/bin/python tests/run.py [substring ...]
"""
from __future__ import annotations

import importlib.util
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def load(path: Path):
    spec = importlib.util.spec_from_file_location(f"tests.{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    mod.__name__ = f"tests.{path.stem}"      # so the __main__ block stays quiet
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str]) -> int:
    files = sorted(HERE.glob("test_*.py"))
    if argv:
        files = [f for f in files if any(a in f.name for a in argv)]

    passed = failed = 0
    failures: list[tuple[str, str]] = []
    for path in files:
        try:
            mod = load(path)
        except Exception:
            failures.append((path.name, traceback.format_exc()))
            failed += 1
            print(f"  IMPORT FAILED  {path.name}")
            continue

        tests = sorted(n for n in vars(mod) if n.startswith("test_")
                       and callable(getattr(mod, n)))
        print(f"\n{path.name}  ({len(tests)} tests)")
        for name in tests:
            t0 = time.time()
            try:
                getattr(mod, name)()
                passed += 1
                print(f"  ok    {name}  ({time.time() - t0:.2f}s)")
            except Exception:
                failed += 1
                failures.append((f"{path.name}::{name}", traceback.format_exc()))
                print(f"  FAIL  {name}")

    for where, tb in failures:
        print(f"\n{'=' * 70}\n{where}\n{'-' * 70}\n{tb.rstrip()}")

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
