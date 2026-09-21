"""The claim that must never silently regress.

These tests do not assert "we are contained". They assert that the system
reports containment *honestly* -- that it cannot show a green badge it is
unable to back with observed evidence. A prototype that lies optimistically
about egress is worse than one that admits it is unenforced.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from app.egress import EgressMonitor
from app.router import Router

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "models.yaml").read_text())


def test_sovereign_allowlist_is_empty():
    """Sovereign mode permits nothing. If this ever grows an entry, the mode is a lie."""
    assert CFG["modes"]["sovereign"]["egress_allow"] == []


def test_prototype_allowlist_is_exactly_one_host():
    allow = CFG["modes"]["prototype"]["egress_allow"]
    assert len(allow) == 1, f"prototype must pin a single host, got {allow}"
    assert allow[0] == "integrate.api.nvidia.com"


def test_sovereign_endpoint_is_not_remote():
    ep = CFG["modes"]["sovereign"]["endpoint"]
    assert any(ep.startswith(f"http://{h}") for h in ("localhost", "127.0.0.1", "ollama")), ep
    assert CFG["modes"]["sovereign"]["api_key_env"] is None, "sovereign mode needs no key"


def test_every_model_resolves_in_both_modes():
    """A tier that exists in one mode but not the other breaks the mode switch."""
    for m in CFG["models"]:
        for mode in ("prototype", "sovereign"):
            assert m.get(mode), f"model {m['id']} has no {mode} backend"


def test_monitor_reports_unverified_without_an_observer(monkeypatch=None):
    """No tcpdump -> status must say UNVERIFIED, never a reassuring green."""
    import app.egress as eg
    real = eg.shutil.which
    eg.shutil.which = lambda _: None
    try:
        m = EgressMonitor(allowlist=[], mode="sovereign")
        asyncio.run(m.start())
        assert "UNVERIFIED" in m.snapshot()["status"]
    finally:
        eg.shutil.which = real


def test_tripwire_does_not_claim_blocked_when_it_got_through():
    """The tripwire must report what actually happened, not what we hoped."""
    m = EgressMonitor(allowlist=[], mode="sovereign")
    r = asyncio.run(m.tripwire("https://api.openai.com/v1/models"))
    assert isinstance(r["blocked"], bool)
    # Whatever the verdict, it must be mirrored into the observable event log.
    assert m.events and m.events[-1].detail.startswith("tripwire:")
    assert (m.events[-1].verdict == "BLOCKED") == r["blocked"]
    if not r["blocked"]:
        # A call that got through to a non-allowlisted host is a LEAK. Labelling
        # it "ALLOWED" would make the worst case look benign in the UI.
        assert m.events[-1].verdict == "LEAKED"
        assert "NOT contained" in r["detail"]
        assert m.snapshot()["leaked_count"] == 1
        assert m.snapshot()["contained"] is False


def test_local_traffic_is_never_counted_as_egress():
    m = EgressMonitor(allowlist=["integrate.api.nvidia.com"], mode="prototype")
    assert m._classify("127.0.0.1.8117") == "LOCAL"
    assert m._classify("172.28.117.4.11434") == "LOCAL"
    assert m._classify("104.18.32.99.443") == "LEAKED"
    assert m._classify("3.33.145.9.443") == "LEAKED"


def test_containment_requires_an_observer_and_zero_leaks():
    """`contained` must be false when unobserved, even with a clean event log."""
    m = EgressMonitor(allowlist=[], mode="sovereign")
    m.status = "UNVERIFIED (tcpdump not installed)"
    assert m.snapshot()["contained"] is False, "unobserved must never read as contained"
    m.status = "MONITORING"
    assert m.snapshot()["contained"] is True


def test_router_mode_matches_egress_mode():
    """A router in sovereign mode must never be paired with a permissive allowlist."""
    r = Router(mode="sovereign")
    assert r.mode_cfg["egress_allow"] == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\nsovereignty: all checks passed")
