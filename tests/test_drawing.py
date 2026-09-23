"""Reading an engineering drawing.

The fixture is drawn by scripts/make_pid_sample.py, so the tags on it are known
exactly and "did the model read it" has an answer rather than an opinion.

These tests cover the machinery -- tiling, tag extraction, degeneration
detection -- without calling a model. Measured accuracy against the live model
is recorded in docs/model-benchmark.md, because it is a property of the model
rather than of this code.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from app.tools import _TAG, _looks_degenerate, _tiles, ROOT

PID = ROOT / "data" / "uploads" / "PID_CDU_P-204.png"
TAGS = ["P-204A", "P-204B", "V-101", "E-102",
        "PI-2041", "TI-2042", "FIC-2043", "LIC-1011", "PSV-1012"]
LINES = ['6"-CR-2041-A1A', '8"-CR-2042-A1A', '4"-CW-1021-B2B']


def test_every_ground_truth_tag_is_extractable():
    """If the pattern cannot match a tag, no amount of model quality helps."""
    found = _TAG.findall(" ".join(TAGS + LINES))
    missing = [t for t in TAGS + LINES if t not in found]
    assert not missing, f"pattern cannot match: {missing}"


def test_line_numbers_are_not_truncated_by_a_shorter_alternative():
    assert _TAG.findall('6"-CR-2041-A1A') == ['6"-CR-2041-A1A']


def test_a_large_sheet_is_tiled_but_a_small_image_is_not():
    assert PID.exists(), "run: make pid"
    big = Image.open(PID)
    assert len(_tiles(big)) > 1, "a full sheet must be split"
    assert len(_tiles(big.resize((600, 400)))) == 1, "a small image must not be"


def test_tiles_overlap_so_a_tag_on_a_seam_survives():
    boxes = [b for b, _ in _tiles(Image.open(PID))]
    xs = sorted({b[0] for b in boxes})
    assert len(xs) > 1
    first_right = max(b[2] for b in boxes if b[0] == xs[0])
    assert first_right > xs[1], "adjacent tiles must overlap"


def test_runaway_numbering_is_caught():
    """A model that loses its place counts: V-102, V-103 ... V-329.

    Recall stays perfect while precision collapses, and an invented tag is
    worse than a missing one on a drawing someone works from.
    """
    text = "\n".join(f"V-{n}" for n in range(101, 140))
    assert _looks_degenerate(text, _TAG.findall(text))


def test_repeated_lines_are_caught():
    text = "\n".join(['* 8"-CR-2042-A1A'] * 20)
    assert _looks_degenerate(text, _TAG.findall(text))


def test_a_genuine_reading_is_not_flagged():
    text = ("V-101 CRUDE SURGE DRUM\nP-204A crude charge pump\n"
            "P-204B standby\nE-102 feed preheater\nPI-2041 pressure indicator")
    assert _looks_degenerate(text, _TAG.findall(text)) is None


def test_consecutive_equipment_numbers_are_allowed_below_the_threshold():
    """Real sheets do carry V-101, V-102, V-103. Only long runs are counting."""
    text = "\n".join(f"V-{n}" for n in range(101, 105))
    assert _looks_degenerate(text, _TAG.findall(text)) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\ndrawing: all checks passed")
