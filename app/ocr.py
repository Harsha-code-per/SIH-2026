"""Document reading.

The first decision is not which model to use, it is whether a model is needed at
all. A digitally-generated PDF already carries its text; running a vision model
over it would be slower, less accurate and entirely pointless. So: check for a
text layer, and only fall through to the document VLM when there isn't one.

That check is itself a routing decision, and the UI shows it.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, asdict
from pathlib import Path

import pymupdf

# Below this many characters a page is treated as scanned. A digital page
# carries hundreds; a scanned one carries a handful of stray glyphs at most.
TEXT_LAYER_MIN_CHARS = 120


@dataclass
class Page:
    page: int
    text: str
    source: str          # "text-layer" | "vlm" | "pending-vlm"
    width: int = 0
    height: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def page_image_b64(path: Path, page_no: int, dpi: int = 200) -> str:
    """Render one page to PNG for the vision model. Never leaves the process."""
    with pymupdf.open(path) as doc:
        pix = doc[page_no - 1].get_pixmap(dpi=dpi)
        return base64.b64encode(pix.tobytes("png")).decode()


def classify_pdf(path: Path) -> dict:
    """Per-page verdict on whether a model is needed. Cheap, deterministic."""
    with pymupdf.open(path) as doc:
        pages = []
        for i, page in enumerate(doc, 1):
            chars = len(page.get_text().strip())
            pages.append({"page": i, "chars": chars,
                          "needs_vlm": chars < TEXT_LAYER_MIN_CHARS})
    scanned = sum(p["needs_vlm"] for p in pages)
    return {
        "pages": len(pages),
        "scanned_pages": scanned,
        "kind": "scanned" if scanned > len(pages) / 2 else "digital",
        "detail": pages,
        "why": (f"{scanned}/{len(pages)} pages carry no text layer "
                f"(<{TEXT_LAYER_MIN_CHARS} chars)"),
    }


def read_pdf(path: Path) -> list[Page]:
    """Extract whatever the text layer gives. Pages without one are marked
    pending-vlm for the caller to send to the document model."""
    out: list[Page] = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, 1):
            text = page.get_text().strip()
            r = page.rect
            out.append(Page(
                page=i, text=text,
                source="text-layer" if len(text) >= TEXT_LAYER_MIN_CHARS else "pending-vlm",
                width=int(r.width), height=int(r.height)))
    return out


PARSE_PROMPT = (
    "Transcribe this document page exactly. Preserve tables as markdown, keep "
    "every number, unit, tag and heading verbatim. Do not summarise, explain or "
    "add commentary. If a value is illegible write [illegible]."
)


async def read_pdf_with_vlm(path: Path, llm, model: str,
                            pages: list[int] | None = None) -> list[Page]:
    """Fill in the pages that have no text layer, using the document model."""
    got = read_pdf(path)
    todo = [p for p in got if p.source == "pending-vlm"
            and (pages is None or p.page in pages)]
    for p in todo:
        p.text = await llm.vision(model, PARSE_PROMPT, page_image_b64(path, p.page))
        p.source = "vlm"
    return got


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def classify_attachment(path: Path) -> dict:
    """What kind of thing is this, and which tier should read it?

    Decided from the file, never from words in the prompt. A scanned report and
    a P&ID are both "an image" to a router that only knows there is one, and
    they need different models.
    """
    if path.suffix.lower() in IMAGE_SUFFIXES:
        return {"kind": "drawing", "tier": "LV2", "has_image": True,
                "why": "an image file, so a photograph or a drawing"}
    if path.suffix.lower() != ".pdf":
        return {"kind": None, "tier": None, "has_image": False,
                "why": "plain text, no model needed to read it"}
    v = classify_pdf(path)
    if v["kind"] == "scanned":
        return {"kind": "page", "tier": "LV", "has_image": True,
                "why": v["why"], "pages": v["pages"],
                "scanned_pages": v["scanned_pages"]}
    return {"kind": None, "tier": None, "has_image": False,
            "why": v["why"] + " -- the text layer is enough",
            "pages": v["pages"]}
