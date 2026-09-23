"""Citation handling. A false 'uncited' verdict costs a needless escalation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import cited_ids, normalise_citations

STYLES = {
    "ascii":      "limit is 7.1 [Maintenance_SOP_v7.md#7]",
    "cjk":        "limit is 7.1 【Maintenance_SOP_v7.md#7】",
    "fullwidth":  "limit is 7.1 ［Maintenance_SOP_v7.md#7］",
    "parens":     "limit is 7.1 (Maintenance_SOP_v7.md#7)",
    "spaced":     "limit is 7.1 [ Maintenance_SOP_v7.md#7 ]",
}


def test_every_bracket_style_is_recognised():
    for name, text in STYLES.items():
        assert cited_ids(text) == {"Maintenance_SOP_v7.md#7"}, f"{name} not matched"


def test_all_styles_normalise_to_ascii():
    for name, text in STYLES.items():
        assert normalise_citations(text).endswith("[Maintenance_SOP_v7.md#7]"), name


def test_multiple_citations_in_one_answer():
    txt = ("Zone D 【Maintenance_SOP_v7.md#7】 and approval "
           "[Maintenance_SOP_v7.md#14] plus (Equipment_Register_Extract.md#0)")
    assert cited_ids(txt) == {"Maintenance_SOP_v7.md#7", "Maintenance_SOP_v7.md#14",
                              "Equipment_Register_Extract.md#0"}


def test_prose_without_citations_is_not_a_false_positive():
    assert cited_ids("The limit is 7.1 mm/s (see the SOP).") == set()
    assert cited_ids("Nothing here at all.") == set()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\nagent citations: all checks passed")


def test_repeat_guards_leave_room_to_answer():
    """Looping must not be able to consume the whole step budget."""
    from app.agent import (MAX_STEPS, REPEATS_BEFORE_WITHDRAWAL,
                           REPEATS_BEFORE_FORCING)
    assert REPEATS_BEFORE_WITHDRAWAL < REPEATS_BEFORE_FORCING < MAX_STEPS / 2, (
        "a model could spend the whole step budget repeating itself and never "
        "reach the deliverable")


def test_a_task_that_retrieved_nothing_is_not_ok():
    """Zero evidence after searching means ungrounded, however good it looks.

    Passing such a run because there were no citations to contradict would
    invert the check: the less it retrieved, the easier it would pass.
    """
    from app.agent import Agent
    from app.router import Router
    a = Agent(Router(), llm=None)
    v = a._verify("Note written.", evidence={}, deliverables=[{"path": "x.docx"}],
                  stdouts=None, searched=True, retrieval_broken="retrieval unavailable")
    assert v == "ungrounded", v
    # Not searching at all is a different case: arithmetic needs no sources.
    assert a._verify("42", evidence={}, deliverables=[], stdouts=None,
                     searched=False) == "ok"


def test_repairable_verdicts_have_actionable_instructions():
    """A retry needs to say what to do differently, or it is just a re-roll."""
    from app.agent import REPAIRABLE
    assert set(REPAIRABLE) == {"uncited", "invented-citation",
                               "fabricated-output", "malformed"}
    for verdict, hint in REPAIRABLE.items():
        assert len(hint) > 60, verdict
        # Each hint must name a concrete corrective action, not just complain.
        assert any(w in hint.lower() for w in
                   ("again", "must", "use only", "either", "report exactly",
                    "run the code")), verdict
    # "empty" and "step-limit" are not listed: retrying them unchanged is a
    # re-roll, not a repair.
    assert "empty" not in REPAIRABLE and "step-limit" not in REPAIRABLE


def test_a_code_task_whose_runs_all_failed_is_not_ok():
    """Six timed-out sandbox runs once produced verdict=ok. Never again."""
    from app.agent import Agent
    from app.router import Router
    a = Agent(Router(), llm=None)
    assert a._verify("The mean is 7.325.", {}, [], stdouts=["", ""],
                     sandbox_runs=2, sandbox_ok=0) == "sandbox-failed"
    # One failure then one success is the loop working as intended.
    assert a._verify("The mean is 7.325.", {}, [], stdouts=["", "7.325"],
                     sandbox_runs=2, sandbox_ok=1) == "ok"


def test_emit_survives_payloads_that_shadow_its_parameters():
    """Tool payloads carry arbitrary keys, including 'kind' and 'label'."""
    from app.agent import Agent
    from app.router import Router
    a = Agent(Router(), llm=None)
    s = a._emit("route", "attachment", **{"kind": "page", "label": "x",
                                          "n": 99, "path": "a.pdf"})
    assert s.kind == "route" and s.label == "attachment" and s.n == 1
    assert s.detail["kind"] == "page" and s.detail["path"] == "a.pdf"
