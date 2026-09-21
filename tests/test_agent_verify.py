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
