"""Page transcription is expensive and deterministic, so it is cached.

A scanned page costs a minute or two of vision-model time and never changes.
Paying that again on every run makes the flagship workflow unusable to
demonstrate, and pointlessly slow in production.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.tools as T

SAMPLE = T.ROOT / "data" / "uploads" / "Inspection_Report_P-204.pdf"


def _clear(p):
    for f in T.CACHE.glob(f"{p.stem}.*"):
        f.unlink()


def test_second_parse_is_served_from_cache():
    assert SAMPLE.exists(), "run: make sample"
    _clear(SAMPLE)
    calls = []
    real = T._ask_vision
    T._ask_vision = lambda *a, **k: (calls.append(a[0]), "TRANSCRIBED TEXT")[1]
    try:
        a = T.parse_page("data/uploads/Inspection_Report_P-204.pdf", 1)
        b = T.parse_page("data/uploads/Inspection_Report_P-204.pdf", 1)
    finally:
        T._ask_vision = real
    assert a["cached"] is False and b["cached"] is True
    assert a["text"] == b["text"] == "TRANSCRIBED TEXT"
    assert len(calls) == 1, f"model called {len(calls)} times, expected 1"


def test_pages_are_cached_independently():
    _clear(SAMPLE)
    calls = []
    real = T._ask_vision
    T._ask_vision = lambda *a, **k: (calls.append(a), f"page text")[1]
    try:
        T.parse_page("data/uploads/Inspection_Report_P-204.pdf", 1)
        T.parse_page("data/uploads/Inspection_Report_P-204.pdf", 2)
        T.parse_page("data/uploads/Inspection_Report_P-204.pdf", 1)
    finally:
        T._ask_vision = real
    assert len(calls) == 2, "page 2 must not reuse page 1's entry"


def test_key_is_content_addressed_so_an_edit_invalidates_it():
    """A changed file must not serve a stale transcription."""
    tmp = T.ROOT / "data" / "uploads" / "_cache_probe.txt"
    tmp.write_bytes(b"one")
    k1 = T._cache_key(tmp, "page", 1)
    tmp.write_bytes(b"two")
    k2 = T._cache_key(tmp, "page", 1)
    tmp.unlink()
    assert k1 != k2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\ncache: all checks passed")
