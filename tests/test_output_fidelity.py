"""An answer must not present numbers as program output unless a tool printed them.

In an engineering context a fabricated number carries exactly the authority of a
real one, so this is checked rather than trusted.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import unbacked_output

REAL = ["Slope: 0.5700 mm/s per month\nIntercept: 6.4700\nMonth to 9.0: 4.44"]


def test_faithful_report_passes():
    answer = ("The fit gives:\n\n**Output**\n```\nSlope: 0.5700 mm/s per month\n"
              "Intercept: 6.4700\n```\nSo it rises steadily.")
    assert unbacked_output(answer, REAL) == []


def test_fabricated_numbers_are_caught():
    answer = ("**Output from the script**\n```\nSlope: 0.5700 mm/s per month\n"
              "Intercept: 5.9000\nPredicted month: 5.44\n```")
    missing = unbacked_output(answer, REAL)
    assert "Intercept: 5.9000" in missing
    assert "Predicted month: 5.44" in missing
    assert "Slope: 0.5700 mm/s per month" not in missing, "real line flagged"


def test_prose_and_source_blocks_are_not_treated_as_output():
    answer = "Here is the script:\n```python\nm = 0.57\nprint(m)\n```\nIt fits a line."
    assert unbacked_output(answer, REAL) == []


def test_no_stdout_means_nothing_to_check():
    assert unbacked_output("**Output**\n```\n42\n```", []) == ["42"]


def test_non_numeric_lines_are_ignored():
    answer = "**Result**\n```\nDone.\nFinished successfully.\n```"
    assert unbacked_output(answer, REAL) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\noutput fidelity: all checks passed")
