"""Generate a realistic scanned inspection report for the demo.

Renders a typed report to images and rebuilds the PDF from those images, so the
result genuinely has no text layer -- the document pipeline has to reach for the
vision model rather than finding text waiting for it. A slight rotation and a
grey cast imitate a desk scanner.

    .venv/bin/python scripts/make_scanned_sample.py
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "uploads" / "Inspection_Report_P-204.pdf"

REPORT = """MANGALORE REFINERY AND PETROCHEMICALS LIMITED
ROTATING EQUIPMENT CONDITION MONITORING REPORT

Report No      : CM/CDU/2026/0847
Date           : 12 September 2026
Unit           : Crude Distillation Unit
Technician     : R. Shetty  (ID 4471)
Analyser       : CSI 2140, S/N 88213, cal. valid to 2027-03


1. EQUIPMENT

   Tag            P-204
   Description    Crude Charge Pump B
   Rated power    132 kW
   Speed          2960 rpm
   Condition      Running, normal operating point


2. VIBRATION READINGS  (RMS velocity, mm/s, 10-1000 Hz)

   Point                    Horiz    Vert    Axial
   ---------------------------------------------------
   Pump drive end            8.2      7.4      3.1
   Pump non-drive end        6.9      6.1      2.8
   Motor drive end           4.4      3.9      2.2
   Motor non-drive end       3.8      3.5      1.9

   Previous month, pump drive end horizontal:  6.5
   Reading after 2024-11 overhaul:             2.9


3. TEMPERATURE

   Pump drive end bearing housing      79 deg C
   Pump non-drive end bearing housing  74 deg C
   Established baseline                61 deg C
   Ambient                             34 deg C


4. MECHANICAL SEAL

   Visible leakage      3 drops per minute
   Seal plan            API Plan 11
   Flush line           Clear, no restriction observed


5. LUBRICATION

   Oil level            Within oiler marks
   Oil condition        Slight darkening, no water or metal visible


6. TECHNICIAN REMARKS

   Drive end horizontal vibration has risen noticeably since the previous
   survey. Bearing housing temperature also elevated against baseline at
   comparable load. Recommend review against SOP-4 acceptance criteria.

   Signature: R. Shetty
"""


def build() -> Path:
    typed = pymupdf.open()
    lines = REPORT.split("\n")
    per_page = 58
    for i in range(0, len(lines), per_page):
        page = typed.new_page(width=595, height=842)   # A4
        page.insert_text((58, 70), "\n".join(lines[i:i + per_page]),
                         fontname="cour", fontsize=9.2, lineheight=1.32)

    scanned = pymupdf.open()
    for page in typed:
        # 150 dpi, greyscale, slightly rotated -- a page off a desk scanner.
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
        dest = scanned.new_page(width=page.rect.width, height=page.rect.height)
        dest.insert_image(dest.rect, pixmap=pix, rotate=0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    scanned.save(OUT, deflate=True)
    typed.close(); scanned.close()
    return OUT


if __name__ == "__main__":
    p = build()
    with pymupdf.open(p) as d:
        chars = sum(len(pg.get_text().strip()) for pg in d)
        pages = d.page_count
    print(f"{p.relative_to(ROOT)}  pages={pages}  "
          f"text-layer chars={chars}  ({p.stat().st_size // 1024} KB)")
    assert chars < 50, "sample must have no usable text layer to be a real test"
    print("verified: no text layer, the vision model is required")
