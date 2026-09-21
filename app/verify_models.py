"""Check every registry id against the live catalogue.

Model ids drift. This turns "the demo 404s on stage" into a one-second check.

    .venv/bin/python -m app.verify_models
"""
from __future__ import annotations

import os
import sys
import urllib.request
import json

from .router import Router


def catalogue(endpoint: str, key: str | None) -> set[str]:
    req = urllib.request.Request(endpoint.rstrip("/") + "/models")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return {m["id"] for m in json.load(r)["data"]}


def main() -> int:
    mode = os.environ.get("MODE", "prototype")
    r = Router(mode=mode)
    key_env = r.mode_cfg.get("api_key_env")
    endpoint = r.mode_cfg["endpoint"]
    try:
        have = catalogue(endpoint, os.environ.get(key_env) if key_env else None)
    except Exception as e:
        print(f"cannot reach {endpoint}: {e}")
        return 2

    bad = 0
    for m in r.models:
        want = r.resolve(m)
        ok = want in have
        bad += not ok
        print(f"  {'ok ' if ok else 'MISSING'}  {m['tier']:<4} {m['id']:<8} {want}")
    print(f"\n{mode}: {len(r.models) - bad}/{len(r.models)} registry ids present in {endpoint}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
