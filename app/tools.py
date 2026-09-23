"""Local tools the agent can call.

Everything here runs on this machine. No tool reaches the network, and the one
that executes model-written code does so with the network removed rather than
merely discouraged.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import operator as op
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .kb import KB

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
UPLOADS = ROOT / "data" / "uploads"
SANDBOX_IMAGE = "wb-sandbox"


# --------------------------------------------------------------------------
# L0: deterministic arithmetic. No model involved, and no eval() either -- the
# AST is walked with an explicit operator whitelist, so a crafted expression
# cannot reach the interpreter.
# --------------------------------------------------------------------------
_OPS: dict[type, Callable] = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
    ast.USub: op.neg, ast.UAdd: op.pos,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"not a number: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def _tidy(value: float) -> float | int:
    """Drop binary floating-point noise.

    8.2 - 7.1 is 1.0999999999999996 in IEEE 754. Correct, and unusable in a
    document a section head signs: an engineering value carries the precision
    of its inputs, not of its representation. Twelve significant digits is far
    beyond any instrument here and removes the artefact.
    """
    if isinstance(value, int):
        return value
    r = round(value, 12)
    return int(r) if r == int(r) and abs(r) < 1e15 else r


def calculate(expression: str) -> dict:
    """Evaluate an arithmetic expression exactly, showing the work."""
    expr = expression.strip().rstrip("=?").strip()
    value = _tidy(_eval(ast.parse(expr, mode="eval").body))
    return {"expression": expr, "result": value,
            "steps": f"{expr} = {value}",
            "engine": "deterministic (no LLM)"}


_NUM = r"-?\d+(?:\.\d+)?"
_PCT = re.compile(
    rf"percent(?:age)?\s+(increase|decrease|change|difference).{{0,20}}?"
    rf"from\s+({_NUM})\s+to\s+({_NUM})", re.I)
# A maximal run of characters that could belong to an expression. Candidates are
# then validated by actually parsing them, which is more reliable than trying to
# describe valid arithmetic in one regex.
_RUN = re.compile(r"[\d.(][\d.\s+\-*/%^()]*")
_HAS_OP = re.compile(r"[+\-*/%^]")


def parse_arithmetic(prompt: str) -> tuple[str, dict]:
    """Turn a natural-language arithmetic request into an exact tool call.

    Deterministic on purpose: the L0 tier exists so that numbers never depend on
    a language model, and that guarantee would be hollow if a model decided what
    the numbers were.
    """
    m = _PCT.search(prompt)
    if m:
        return "percent_change", {"before": float(m.group(2)), "after": float(m.group(3))}

    text = prompt.replace("\u00d7", "*").replace("\u00f7", "/")
    best = ""
    for run in _RUN.findall(text):
        # Trim from the right until what remains actually parses -- "8.2 to" and
        # trailing punctuation are common and must not sink the whole candidate.
        cand = run.strip()
        while cand:
            if _HAS_OP.search(cand) and any(c.isdigit() for c in cand):
                try:
                    ast.parse(cand, mode="eval")
                    break
                except SyntaxError:
                    pass
            cand = cand[:-1].strip()
        if len(cand) > len(best):
            best = cand
    if best:
        return "calculate", {"expression": best}
    raise ValueError(f"no arithmetic found in {prompt!r}")


def percent_change(before: float, after: float) -> dict:
    pct = _tidy(round((after - before) / before * 100, 4))
    return {"before": before, "after": after, "result": pct,
            "steps": f"({after} - {before}) / {before} x 100 = {pct}%",
            "engine": "deterministic (no LLM)"}


# --------------------------------------------------------------------------
# Knowledge base
# --------------------------------------------------------------------------
def kb_search(query: str, k: int = 6) -> dict:
    """Search local SOPs and manuals. Returns passages with their provenance."""
    if KB.vectors is None:
        KB.load()
    if not KB.chunks:
        return {"error": "knowledge base is empty -- run the index build first",
                "query": query, "count": 0, "passages": []}
    try:
        hits = KB.search(query, k=k)
    except Exception as e:
        # An unavailable index is a broken system, not an empty result set.
        # Returning zero passages here once let a document be written with
        # nothing behind it.
        return {"error": f"retrieval unavailable: {type(e).__name__}: {e}",
                "query": query, "count": 0, "passages": []}
    return {"query": query, "count": len(hits),
            "passages": [{"id": h["id"], "cite": h["cite"], "score": h["score"],
                          "text": h["text"]} for h in hits]}


def read_document(path: str) -> dict:
    """Read an uploaded document. Reports which pages need the vision model."""
    from .ocr import classify_pdf, read_pdf
    p = (ROOT / path) if not Path(path).is_absolute() else Path(path)
    p = p.resolve()
    # Path containment: a model-supplied path must not escape the data directory.
    if not p.is_relative_to(ROOT / "data"):
        raise ValueError(f"refusing to read outside data/: {path}")
    if p.suffix.lower() != ".pdf":
        return {"path": str(p.relative_to(ROOT)), "kind": "text",
                "text": p.read_text(errors="replace")}
    verdict = classify_pdf(p)
    return {"path": str(p.relative_to(ROOT)), **verdict,
            "pages_text": [pg.as_dict() for pg in read_pdf(p)]}


# --------------------------------------------------------------------------
# Sandboxed code execution
# --------------------------------------------------------------------------
def run_python(code: str, timeout: int = 20) -> dict:
    """Execute model-written Python in a container with no network at all.

    --network none is the load-bearing flag: the sandbox cannot phone home even
    if the code it was handed tries to.

    The snippet arrives on stdin rather than a bind mount. When the app itself
    runs in a container and talks to the host's Docker daemon, a mount path
    would be resolved on the host, where the app's temp directory does not
    exist. stdin has no path to get wrong.
    """
    cmd = [
        "docker", "run", "--rm", "-i",
        "--network", "none",              # no egress, at all
        "--memory", "512m", "--pids-limit", "64", "--cpus", "1",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:size=16m",
        SANDBOX_IMAGE, "python", "-",
    ]
    try:
        r = subprocess.run(cmd, input=code, capture_output=True, text=True,
                           timeout=timeout + 10)
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"timed out after {timeout}s",
                "exit_code": None, "isolation": "--network none"}
    except FileNotFoundError:
        return {"ok": False, "stdout": "",
                "stderr": "docker CLI not available to the app; the sandbox cannot start",
                "exit_code": None, "isolation": "none"}
    return {"ok": r.returncode == 0, "stdout": r.stdout[-4000:],
            "stderr": r.stderr[-2000:], "exit_code": r.returncode,
            "isolation": "--network none --cap-drop ALL --read-only"}


# --------------------------------------------------------------------------
# Deliverables
# --------------------------------------------------------------------------
_MD_ROW = re.compile(r"^\s*\|.*\|\s*$")
_MD_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def _split_markdown_tables(body: str) -> list[tuple[str, object]]:
    """Separate prose from markdown tables.

    Models write tables as markdown even when handed a table parameter. Pasting
    that into a Word paragraph produces pipes and dashes in a document meant for
    a section head, so it is parsed into real rows instead.
    """
    out: list[tuple[str, object]] = []
    prose: list[str] = []
    rows: list[list[str]] = []

    def flush_prose():
        if prose and "".join(prose).strip():
            out.append(("text", "\n".join(prose).strip()))
        prose.clear()

    def flush_rows():
        if rows:
            out.append(("table", [r[:] for r in rows]))
        rows.clear()

    for line in body.splitlines():
        if _MD_ROW.match(line):
            if _MD_RULE.match(line):      # the |---|---| separator
                continue
            flush_prose()
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        else:
            flush_rows()
            prose.append(line)
    flush_prose(); flush_rows()
    return out


def write_docx(title: str, sections: list[dict], filename: str = "Approval_Note.docx",
               subtitle: str | None = None) -> dict:
    """Write a Word deliverable. `sections` is [{heading, body, table?}]."""
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    OUT.mkdir(parents=True, exist_ok=True)
    doc = Document()
    h = doc.add_heading(title, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if subtitle:
        p = doc.add_paragraph(subtitle)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].italic = True

    for s in sections:
        if s.get("heading"):
            doc.add_heading(str(s["heading"]), level=1)
        # Models do not reliably use the key the schema names. Dropping the
        # content silently produced a note that was nothing but headings and
        # source lines, so aliases are accepted and an unrecognised shape is
        # an error rather than an empty section.
        if not s.get("body"):
            for alias in ("text", "content", "paragraphs", "value"):
                if s.get(alias):
                    v = s[alias]
                    s["body"] = "\n\n".join(map(str, v)) if isinstance(v, list) else str(v)
                    break
        if s.get("heading") and not s.get("body") and not s.get("table"):
            raise ValueError(
                f"section {s.get('heading')!r} has no body. Put the text in "
                f"'body' as a string; got keys {sorted(s)}")
        if s.get("body"):
            for kind, chunk in _split_markdown_tables(str(s["body"])):
                if kind == "table":
                    _add_table(doc, chunk)
                else:
                    for para in chunk.split("\n\n"):
                        if para.strip():
                            doc.add_paragraph(para.strip())
        if s.get("table"):
            _add_table(doc, s["table"])
        if s.get("citations"):
            # Bracketed, because that is the form everything downstream reads:
            # an unbracketed id was not recognised as a citation and a properly
            # sourced note was failing verification.
            cites = [c if c.startswith("[") else f"[{c}]" for c in s["citations"]]
            p = doc.add_paragraph()
            r = p.add_run("Source: " + " ".join(cites))
            r.italic = True
            r.font.size = Pt(9)

    dest = OUT / Path(filename).name
    doc.save(dest)
    return {"path": str(dest.relative_to(ROOT)), "bytes": dest.stat().st_size,
            "download": f"/api/download/{dest.name}"}


def _add_table(doc, rows: list[list]) -> None:
    rows = [r for r in rows if r]
    if not rows:
        return
    width = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=width)
    t.style = "Table Grid"
    for ri, row in enumerate(rows):
        for ci in range(width):
            cell = t.cell(ri, ci)
            cell.text = str(row[ci]) if ci < len(row) else ""
            if ri == 0:
                for run in cell.paragraphs[0].runs:
                    run.bold = True


def write_xlsx(filename: str, sheet: str, rows: list[list]) -> dict:
    from openpyxl import Workbook
    OUT.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    for row in rows:
        ws.append(row)
    for c in ws[1]:
        c.font = c.font.copy(bold=True)
    dest = OUT / Path(filename).name
    wb.save(dest)
    return {"path": str(dest.relative_to(ROOT)), "bytes": dest.stat().st_size,
            "download": f"/api/download/{dest.name}"}


# --------------------------------------------------------------------------
# Registry the agent loop advertises to the model
# --------------------------------------------------------------------------
@dataclass
class Tool:
    fn: Callable
    schema: dict


def _t(name: str, desc: str, props: dict, required: list[str], fn: Callable) -> Tool:
    return Tool(fn, {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}})


TOOLS: dict[str, Tool] = {
    "kb_search": _t("kb_search",
        "Search the organisation's local SOPs, procedures and equipment register. "
        "Returns passages with citations. Use this before stating any requirement or limit.",
        {"query": {"type": "string", "description": "What to look for"},
         "k": {"type": "integer", "description": "How many passages (default 6)"}},
        ["query"], kb_search),

    "read_document": _t("read_document",
        "Read an uploaded document from data/uploads. Returns page text and flags "
        "pages that have no text layer.",
        {"path": {"type": "string", "description": "Path such as data/uploads/report.pdf"}},
        ["path"], read_document),

    "calculate": _t("calculate",
        "Evaluate an arithmetic expression exactly. Use this for every number you "
        "report -- never compute mentally.",
        {"expression": {"type": "string", "description": "e.g. (8.2 - 6.5) / 6.5 * 100"}},
        ["expression"], calculate),

    "percent_change": _t("percent_change",
        "Percentage change between two values, computed exactly.",
        {"before": {"type": "number"}, "after": {"type": "number"}},
        ["before", "after"], percent_change),

    "run_python": _t("run_python",
        "Execute Python in an isolated sandbox with no network access. numpy and "
        "pandas are available. Print results to stdout.",
        {"code": {"type": "string", "description": "Python source to run"}},
        ["code"], run_python),

    "write_docx": _t("write_docx",
        "Produce a Word document deliverable. Each section may carry a heading, "
        "body text, a table (list of rows) and citations (list of source strings).",
        {"title": {"type": "string"},
         "subtitle": {"type": "string"},
         "filename": {"type": "string", "description": "e.g. Approval_Note.docx"},
         "sections": {"type": "array", "items": {"type": "object"}}},
        ["title", "sections"], write_docx),

    "write_xlsx": _t("write_xlsx",
        "Produce an Excel deliverable from rows, first row treated as header.",
        {"filename": {"type": "string"}, "sheet": {"type": "string"},
         "rows": {"type": "array", "items": {"type": "array"}}},
        ["filename", "sheet", "rows"], write_xlsx),
}


def schemas(names: list[str] | None = None) -> list[dict]:
    return [t.schema for n, t in TOOLS.items() if names is None or n in names]


def call(name: str, arguments: str | dict) -> Any:
    if name not in TOOLS:
        return {"error": f"unknown tool {name!r}"}
    args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    try:
        return TOOLS[name].fn(**args)
    except Exception as e:
        # Errors are returned to the model rather than raised, so it can correct
        # itself -- that iteration is the point of an agent loop.
        return {"error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------
# Vision: pages with no text layer, and engineering drawings
#
# A synchronous client of its own, because tools are invoked from a worker
# thread. It reads the same mode configuration as everything else, so it moves
# endpoint with the rest of the system.
# --------------------------------------------------------------------------
_vision_client = None


def _vision():
    global _vision_client
    if _vision_client is None:
        import os
        from openai import OpenAI
        from .router import Router
        r = Router()
        key_env = r.mode_cfg.get("api_key_env")
        _vision_client = (OpenAI(
            base_url=os.environ.get("MODEL_ENDPOINT", r.mode_cfg["endpoint"]),
            api_key=os.environ.get(key_env, "") if key_env else "not-needed",
            timeout=180.0), r)
    return _vision_client


def _vision_model(tier: str) -> str:
    _, r = _vision()
    for m in r.models_for_tier(tier):
        return r.resolve(m)
    raise RuntimeError(f"no model registered for tier {tier}")


def _ask_vision(tier: str, prompt: str, image_b64: str, max_tokens: int = 2000) -> str:
    client, _ = _vision()
    r = client.chat.completions.create(
        model=_vision_model(tier), max_tokens=max_tokens, temperature=0.0,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{image_b64}"}}]}])
    return (r.choices[0].message.content or "").strip()


CACHE = ROOT / "data" / "cache"


def _cache_key(p: Path, *parts: str) -> Path:
    """Content-addressed, so editing a file invalidates its own entries."""
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    tail = "-".join(str(x) for x in parts)
    return CACHE / f"{p.stem}.{h}.{tail}.json"


def parse_page(path: str, page: int) -> dict:
    """Transcribe one scanned page with the document model.

    Only for pages that have no text layer -- read_document says which.

    Transcriptions are cached on disk, keyed by the file's own hash. A page
    takes a minute or two to transcribe and the result does not change, so
    re-reading the same report -- which is exactly what happens when a workflow
    is run twice, or demonstrated -- should not pay for it again.
    """
    from .ocr import PARSE_PROMPT, page_image_b64
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT / "data"):
        raise ValueError(f"refusing to read outside data/: {path}")

    key = _cache_key(p, "page", page)
    if key.exists():
        return json.loads(key.read_text()) | {"cached": True}

    text = _ask_vision("LV", PARSE_PROMPT, page_image_b64(p, page))
    out = {"path": path, "page": page, "source": "vlm", "text": text}
    CACHE.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(out))
    return out | {"cached": False}


# Above this, a drawing is read in overlapping tiles rather than whole.
# A P&ID sheet is mostly white space with small text, and sending the whole
# sheet downscales a tag like "FIC-2043" to a few pixels tall -- measured, the
# models read 4 of 9 tags that way. Tiles give each region the model's full
# resolution budget.
TILE_ABOVE_PX = 1500
TILE_OVERLAP = 0.12          # so a tag on a seam is whole in one tile


def _tiles(img, max_px: int = TILE_ABOVE_PX):
    """Split into overlapping tiles, or yield the image whole if it is small."""
    from PIL import Image
    w, h = img.size
    if max(w, h) <= max_px:
        return [((0, 0, w, h), img)]
    # Ceiling, not rounding: a sheet 1.5 tiles tall still needs two rows, and
    # rounding down leaves the text as small as it was.
    import math
    cols = max(1, math.ceil(w / (max_px * 0.8)))
    rows = max(1, math.ceil(h / (max_px * 0.8)))
    ox, oy = int(w / cols * TILE_OVERLAP), int(h / rows * TILE_OVERLAP)
    out = []
    for r in range(rows):
        for c in range(cols):
            box = (max(0, int(c * w / cols) - ox), max(0, int(r * h / rows) - oy),
                   min(w, int((c + 1) * w / cols) + ox),
                   min(h, int((r + 1) * h / rows) + oy))
            out.append((box, img.crop(box)))
    return out


def _b64_png(img) -> str:
    import base64, io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# Ordered longest-first: a line number like 6"-CR-2041-A1A must not be cut
# short by an equipment-tag alternative matching its prefix.
_TAG = re.compile(
    r'\d+"-[A-Z]{2,3}-\d{3,4}-[A-Z0-9]+'     # line number
    r'|\b[A-Z]{1,4}-\d{3,4}[A-Z]?\b'          # tag: V-101, P-204A, LIC-1011
)


def _looks_degenerate(text: str, tags: list[str]) -> str | None:
    """Has the model stopped reading and started counting?

    A vision model that loses its place emits a plausible-looking sequence --
    V-102, V-103, ... V-329 -- from a sheet holding one vessel. Recall stays
    perfect and precision collapses, which is the worse failure: an engineer
    can work with a missing tag and cannot work with an invented one.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) > 12 and len(set(lines)) / len(lines) < 0.5:
        return "repeated lines"
    # A run of consecutive numbers within one prefix is counting, not reading.
    by_prefix: dict[str, list[int]] = {}
    for t in tags:
        m = re.match(r"^([A-Z]{1,4})-(\d{2,4})", t)
        if m:
            by_prefix.setdefault(m.group(1), []).append(int(m.group(2)))
    for prefix, nums in by_prefix.items():
        nums = sorted(set(nums))
        run = best = 1
        for a, b in zip(nums, nums[1:]):
            run = run + 1 if b == a + 1 else 1
            best = max(best, run)
        if best >= 6:
            return f"consecutive run of {best} in {prefix}-"
    return None


def describe_image(path: str, question: str = "") -> dict:
    """Read a photograph or engineering drawing (P&ID, schematic, sketch)."""
    import base64
    from PIL import Image
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT / "data"):
        raise ValueError(f"refusing to read outside data/: {path}")
    if p.suffix.lower() == ".pdf":
        from .ocr import page_image_b64
        b64 = page_image_b64(p, 1)
    else:
        b64 = base64.b64encode(p.read_bytes()).decode()
    prompt = question or (
        "Read this engineering drawing (P&ID). List every equipment tag, "
        "instrument tag and line number exactly as printed.\n"
        # ISA-5.1 draws an instrument as a circle with the function letters on
        # one line and the loop number on the next. Read literally, that is two
        # fragments, and every instrument on the sheet was being missed.
        "An instrument is drawn as a circle containing two lines of text: the "
        "function letters on top and the loop number underneath. Report each as "
        "a single tag joined by a hyphen -- a circle reading 'PI' above '2041' "
        "is the tag PI-2041.\n"
        "Equipment is a box or a pump symbol with its tag beside it, such as "
        "V-101 or P-204A. Line numbers look like 6\"-CR-2041-A1A.\n"
        "If you cannot read something, say so rather than guessing.")
    key = _cache_key(p, "img", hashlib.sha256(prompt.encode()).hexdigest()[:8])
    if key.exists():
        return json.loads(key.read_text()) | {"cached": True}

    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    tiles = _tiles(img)

    def read(i_tile):
        i, (_, tile) = i_tile
        where = "" if len(tiles) == 1 else (
            f" This is region {i} of {len(tiles)} of a larger drawing; "
            f"describe only what is visible here.")
        png = _b64_png(tile)
        said = _ask_vision("LV2", prompt + where, png)
        bad = _looks_degenerate(said, _TAG.findall(said))
        if bad:
            # One retry with a tighter cap; a shorter budget rarely runs away.
            said = _ask_vision("LV2", prompt + where, png, max_tokens=700)
            bad = _looks_degenerate(said, _TAG.findall(said))
        return i, said, bad

    # Tiles are independent, and reading them one at a time made a single sheet
    # take six minutes.
    parts, tags, discarded = [], [], []
    with ThreadPoolExecutor(max_workers=min(4, len(tiles))) as pool:
        for i, said, bad in sorted(pool.map(read, enumerate(tiles, 1))):
            if bad:
                discarded.append({"region": i, "reason": bad})
                continue
            parts.append(said if len(tiles) == 1 else f"[region {i}] {said}")
            tags += _TAG.findall(said)

    # Tiles overlap, so the same tag appears more than once. Order-preserving
    # de-duplication keeps the reading order a person would expect.
    seen, unique = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    out = {"path": path, "source": "vlm", "tiles": len(tiles),
           "tags_found": unique, "description": "\n\n".join(parts)}
    if discarded:
        # Said plainly rather than hidden: a region that could not be read is
        # a gap in the answer, and the reader should know which one.
        out["unreadable_regions"] = discarded
        out["description"] += ("\n\nRegions not reported: " + ", ".join(
            f"region {d['region']} ({d['reason']})" for d in discarded))
    CACHE.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(out))
    return out | {"cached": False}


TOOLS["parse_page"] = _t("parse_page",
    "Transcribe a single scanned page that has no text layer, using the document "
    "model. Call read_document first to find out which pages need this.",
    {"path": {"type": "string"}, "page": {"type": "integer"}},
    ["path", "page"], parse_page)

TOOLS["describe_image"] = _t("describe_image",
    "Read a photograph or engineering drawing such as a P&ID. Returns equipment "
    "and instrument tags as printed.",
    {"path": {"type": "string"},
     "question": {"type": "string", "description": "Optional specific question"}},
    ["path"], describe_image)
