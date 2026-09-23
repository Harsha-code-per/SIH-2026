"""Draw a small P&ID for the multimodal demo.

Drawn rather than downloaded: the problem statement says open sources may be
used, but a synthetic sheet has a known answer, so "did the model read the tags
correctly" has a checkable ground truth instead of a judgement call. The
symbols follow ISA-5.1 conventions closely enough to be read as a P&ID.

    .venv/bin/python scripts/make_pid_sample.py
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "uploads" / "PID_CDU_P-204.png"

# Ground truth, asserted below and reused by the tests.
TAGS = ["P-204A", "P-204B", "V-101", "E-102",
        "PI-2041", "TI-2042", "FIC-2043", "LIC-1011", "PSV-1012"]
LINES = ['6"-CR-2041-A1A', '8"-CR-2042-A1A', '4"-CW-1021-B2B']


def draw() -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)          # A4 landscape
    blk, thin = (0, 0, 0), 0.7

    def text(x, y, s, size=7.5, bold=False):
        page.insert_text((x, y), s, fontsize=size,
                         fontname="hebo" if bold else "helv", color=blk)

    def box(x, y, w, h, label="", tag="", tag_below=False):
        page.draw_rect(pymupdf.Rect(x, y, x + w, y + h), color=blk, width=thin)
        if label:
            text(x + 4, y + 12, label, 7)
        if tag:
            # Below the box where a line label would otherwise collide with it.
            text(x + 4, y + h + 12 if tag_below else y + h - 5, tag, 7.5, bold=True)

    def bubble(cx, cy, tag):
        """ISA-5.1 instrument bubble: a circle with the tag inside."""
        page.draw_circle(pymupdf.Point(cx, cy), 13, color=blk, width=thin)
        text(cx - 12, cy - 1, tag.split("-")[0], 6.5, bold=True)
        text(cx - 12, cy + 7, tag.split("-")[1], 6.5)

    def line(x1, y1, x2, y2, label=""):
        page.draw_line(pymupdf.Point(x1, y1), pymupdf.Point(x2, y2),
                       color=blk, width=1.1)
        if label:
            text((x1 + x2) / 2 - 34, min(y1, y2) - 4, label, 6)

    def pump(x, y, tag):
        """Centrifugal pump: circle on a baseline, ISA style."""
        page.draw_circle(pymupdf.Point(x, y), 16, color=blk, width=thin)
        page.draw_line(pymupdf.Point(x - 22, y + 20), pymupdf.Point(x + 22, y + 20),
                       color=blk, width=thin)
        text(x - 16, y + 32, tag, 8, bold=True)

    # title block
    page.draw_rect(pymupdf.Rect(560, 500, 822, 575), color=blk, width=thin)
    text(568, 515, "MANGALORE REFINERY AND PETROCHEMICALS LTD", 7, bold=True)
    text(568, 528, "CRUDE DISTILLATION UNIT", 7)
    text(568, 541, "P&ID - CRUDE CHARGE PUMPS", 7)
    text(568, 554, "DWG No. PID-CDU-204   REV 3", 6.5)
    text(568, 566, "SHEET 1 OF 1", 6.5)
    page.draw_rect(pymupdf.Rect(20, 20, 822, 575), color=blk, width=1.1)

    # vessel -> pumps -> exchanger, spread over the full sheet
    box(70, 170, 100, 210, "CRUDE SURGE DRUM", "V-101")
    bubble(120, 130, "LIC-1011")
    bubble(200, 130, "PSV-1012")
    line(120, 143, 120, 170)

    line(170, 270, 270, 270, '6"-CR-2041-A1A')
    pump(310, 270, "P-204A")
    line(170, 360, 270, 360)
    pump(310, 370, "P-204B")

    bubble(310, 190, "PI-2041")
    line(310, 203, 310, 254)
    bubble(430, 190, "TI-2042")
    bubble(530, 190, "FIC-2043")

    line(335, 270, 620, 270, '8"-CR-2042-A1A')
    line(335, 370, 470, 370)
    line(470, 370, 470, 270)

    box(620, 220, 130, 110, "FEED PREHEATER", "E-102", tag_below=True)
    # Cooling water enters from below; label sits clear of the exchanger tag.
    line(685, 460, 685, 330)
    text(695, 400, '4"-CW-1021-B2B', 6)

    text(70, 470, "NOTES:", 7, bold=True)
    text(70, 486, "1. P-204A OPERATING, P-204B STANDBY.", 6.5)
    text(70, 499, "2. ALL LINES CS UNLESS NOTED.", 6.5)
    text(70, 512, "3. INSTRUMENT AIR FAIL POSITION: FIC-2043 FAILS CLOSED.", 6.5)

    pix = page.get_pixmap(dpi=200)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pix.save(OUT)
    doc.close()
    return OUT


if __name__ == "__main__":
    p = draw()
    print(f"{p.relative_to(ROOT)}  ({p.stat().st_size // 1024} KB)")
    print(f"ground truth: {len(TAGS)} tags, {len(LINES)} line numbers")
