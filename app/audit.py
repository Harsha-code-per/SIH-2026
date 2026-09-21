"""Append-only run log.

One JSON object per line, written as the run happens. Plain text on purpose:
an auditor with `grep` should not need our software to read it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "data" / "audit.jsonl"


def record(kind: str, **fields) -> dict:
    entry = {"ts": time.time(), "kind": kind, **fields}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry


def tail(n: int = 200) -> list[dict]:
    if not LOG.exists():
        return []
    lines = LOG.read_text().splitlines()[-n:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return out
