"""L0 exists so numbers never depend on a language model.

That guarantee is only real if the expression is extracted deterministically,
so these cover the parsing as well as the evaluation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import parse_arithmetic, calculate, percent_change


def test_percent_change_phrasings():
    for p in ["Calculate the percentage increase from 6.5 to 8.2",
              "what is the percent increase from 6.5 to 8.2",
              "percentage change from 6.5 to 8.2 please"]:
        name, args = parse_arithmetic(p)
        assert name == "percent_change", p
        assert args == {"before": 6.5, "after": 8.2}, p


def test_bare_expressions():
    for p, want in [("What is 18 * 47?", "18 * 47"),
                    ("compute (8.2 - 6.5) / 6.5 * 100", "(8.2 - 6.5) / 6.5 * 100"),
                    ("7.1 + 2.8", "7.1 + 2.8")]:
        name, args = parse_arithmetic(p)
        assert name == "calculate", p
        assert args["expression"] == want, f"{p}: got {args['expression']!r}"


def test_results_are_exact():
    assert calculate("18 * 47")["result"] == 846
    assert percent_change(6.5, 8.2)["result"] == 26.1538
    # Floating point is floating point; assert the value, not a rounded string.
    assert abs(calculate("(8.2 - 6.5) / 6.5 * 100")["result"] - 26.153846) < 1e-5


def test_no_llm_involved():
    for r in (calculate("2+2"), percent_change(1, 2)):
        assert "no LLM" in r["engine"]


def test_hostile_expressions_are_refused():
    for bad in ["__import__('os').system('id')", "open('/etc/passwd').read()",
                "(1).__class__.__bases__"]:
        try:
            calculate(bad)
            assert False, f"should have refused {bad!r}"
        except (ValueError, SyntaxError):
            pass


def test_unparseable_prompt_raises_rather_than_guessing():
    try:
        parse_arithmetic("summarise the maintenance policy")
        assert False, "should not invent an expression"
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\narithmetic: all checks passed")
