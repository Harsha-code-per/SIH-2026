"""The sandbox must contain what it runs.

These assert the isolation flags actually bite, not that the syntax is right.
If any of these start passing network traffic, the sovereignty claim is void
regardless of what the egress monitor says.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import run_python, read_document


def test_it_runs_ordinary_code():
    r = run_python("print(sum(range(10)))")
    assert r["ok"] and r["stdout"].strip() == "45", r


def test_numpy_is_available():
    r = run_python("import numpy as np; print(np.mean([6.5, 8.2]))")
    assert r["ok"] and r["stdout"].strip() == "7.35", r


def test_network_is_unreachable():
    """--network none is the load-bearing flag. This is the one that matters."""
    r = run_python(
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=3)\n"
        "    print('REACHED')\n"
        "except OSError as e:\n"
        "    print('UNREACHABLE')\n")
    assert "UNREACHABLE" in r["stdout"], f"sandbox reached the network: {r}"
    assert "REACHED" not in r["stdout"]


def test_dns_does_not_resolve():
    r = run_python(
        "import socket\n"
        "try: print('RESOLVED', socket.gethostbyname('api.openai.com'))\n"
        "except Exception as e: print('NO-DNS')\n")
    assert "NO-DNS" in r["stdout"], r


def test_filesystem_is_read_only():
    r = run_python("open('/escape.txt','w').write('x'); print('WROTE')")
    assert "WROTE" not in r["stdout"], "sandbox root should be read-only"


def test_failure_is_reported_not_raised():
    r = run_python("raise ValueError('deliberate')")
    assert not r["ok"] and "ValueError" in r["stderr"]


def test_timeout_is_survivable():
    r = run_python("while True: pass", timeout=5)
    assert not r["ok"]


def test_read_document_refuses_to_escape_data_dir():
    """A model-supplied path must not be able to read /etc/passwd."""
    for bad in ("../../etc/passwd", "/etc/passwd", "data/../../etc/hosts"):
        try:
            read_document(bad)
            assert False, f"should have refused {bad!r}"
        except (ValueError, FileNotFoundError):
            pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\nsandbox: all checks passed")
