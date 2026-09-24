"""Router truth table. Pure logic -- runs in milliseconds, needs no GPU or network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.router import Router, extract_features

CASES = [
    # (prompt, has_image, expected_tier, expected_rule)
    ("Calculate the percentage increase from 6.5 to 8.2", False, "L0", "deterministic-math"),
    ("What is 18 * 47?",                                  False, "L0", "deterministic-math"),
    ("Summarize this memo",                               False, "L1", "quick-text"),
    ("Hello, who are you?",                               False, "L1", "default"),
    ("Write a python script to compute the vibration trend", False, "L2", "code-task"),
    ("Analyze this inspection report against the SOP",    False, "L2", "multi-step"),
    ("Read this scanned page",                            True,  "LV", "scanned-document"),
    ("Identify the equipment tags in this P&ID",          True,  "LV2", "engineering-drawing"),
    ("x" * 20000,                                         False, "L2", "long-input"),
    # "compute" in a multi-step request must not drag it down to L0.
    ("Check P-204 against the SOP, compute the rise, and produce an approval note "
     "as a Word document",                                False, "L2", "multi-step"),
    ("Draft a Word document summarising last month's readings",
                                                          False, "L2", "multi-step"),
]


def test_routing_table():
    r = Router()
    for prompt, has_image, tier, rule in CASES:
        d = r.route(prompt, has_image=has_image)
        assert d.tier == tier, f"{prompt[:40]!r}: tier {d.tier} != {tier}"
        assert d.rule == rule, f"{prompt[:40]!r}: rule {d.rule} != {rule}"
        # Every non-L0 decision must name a model that exists in the registry.
        if tier != "L0":
            assert d.model_name, f"{prompt[:40]!r}: no model resolved for {tier}"


def test_arithmetic_never_reaches_an_llm():
    d = Router().route("Calculate the percentage increase from 6.5 to 8.2")
    assert d.model_id is None and d.tool == "calculate"


def test_escalation_goes_up_then_stops():
    r = Router()
    l1 = r.route("Summarize this memo")
    l2 = r.escalate(l1)
    assert l2 and l2.tier == "L2"
    assert r.escalate(l2) is None, "L2 must be the ceiling, not a loop"


def test_mode_switch_changes_model_not_routing():
    proto = Router(mode="prototype").route("Analyze this report against the SOP")
    sov = Router(mode="sovereign").route("Analyze this report against the SOP")
    assert proto.tier == sov.tier == "L2"
    assert proto.model_name != sov.model_name, "modes must resolve different backends"


def test_features_are_explainable():
    f = extract_features("Write a python function", has_image=False)
    assert f.task == "code" and f.needs_tools


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\nrouter: all checks passed")


def test_the_orchestrator_can_call_tools():
    """The vision tiers read images; they cannot drive a tool-calling loop.

    Handing the loop to one made the model print a JSON tool call as its
    final answer.
    """
    r = Router()
    o = r.orchestrator()
    assert o is not None and "tools" in o["caps"]
    assert o["tier"] == "L2", f"expected the strongest tool-capable tier, got {o['tier']}"


def test_engineering_questions_reach_the_analysis_tier():
    """A short question can still be multi-hop work.

    "What zone is 8.2 mm/s?" reads like chat and needs the SOP retrieved and
    a comparison made. Routing it to the cheap tier made it slow and wrong.
    """
    r = Router()
    for q in ["Pump P-204 drive-end vibration is 8.2 mm/s RMS. What zone is that?",
              "Is the bearing at 79 deg C acceptable?",
              "What action does that require?",
              "What is the vibration limit?",
              "Check P-204 against the baseline"]:
        assert r.route(q).tier == "L2", f"{q!r} routed to {r.route(q).tier}"


def test_genuinely_cheap_work_stays_cheap():
    r = Router()
    for q in ["Summarize this memo", "Hello, who are you?", "Thanks, that helps"]:
        assert r.route(q).tier == "L1", f"{q!r} routed to {r.route(q).tier}"


def test_a_manual_choice_overrides_routing_and_says_so():
    """Arithmetic would go to L0; a person who picks the reasoning model gets
    it, and the decision records that it was their choice, not a rule."""
    r = Router()
    d = r.route("What is 18 * 47?", choose="reason")
    assert (d.tier, d.model_id, d.rule) == ("L2", "reason", "manual")
    assert d.escalates_to == r.escalation.get("L2")


def test_an_unknown_manual_choice_is_refused():
    try:
        Router().route("hello", choose="gpt-4o")
    except ValueError:
        return
    raise AssertionError("a model outside the registry was accepted")
