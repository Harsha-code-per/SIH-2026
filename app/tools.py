"""Local tools the agent can call.

Everything here runs on this machine. No tool reaches the network, and the one
that executes model-written code does so with the network removed rather than
merely discouraged.
"""
from __future__ import annotations

import ast
import json
import re
import operator as op
import subprocess
import tempfile
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


def calculate(expression: str) -> dict:
    """Evaluate an arithmetic expression exactly, showing the work."""
    expr = expression.strip().rstrip("=?").strip()
    value = _eval(ast.parse(expr, mode="eval").body)
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
    pct = (after - before) / before * 100
    return {"before": before, "after": after,
            "result": round(pct, 4),
            "steps": f"({after} - {before}) / {before} x 100 = {pct:.4f}%",
            "engine": "deterministic (no LLM)"}


# --------------------------------------------------------------------------
# Knowledge base
# --------------------------------------------------------------------------
def kb_search(query: str, k: int = 6) -> dict:
    """Search local SOPs and manuals. Returns passages with their provenance."""
    if KB.vectors is None:
        KB.load()
    hits = KB.search(query, k=k)
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
    """
    with tempfile.TemporaryDirectory() as tmp:
        snippet = Path(tmp) / "snippet.py"
        snippet.write_text(code)
        # The sandbox runs as an unprivileged uid that is not ours, so the bind
        # mount has to be readable by it. 0755/0644, never writable.
        Path(tmp).chmod(0o755)
        snippet.chmod(0o644)
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",              # no egress, at all
            "--memory", "512m", "--pids-limit", "64", "--cpus", "1",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp:size=16m",
            "-v", f"{tmp}:/work:ro",
            SANDBOX_IMAGE, "python", "/work/snippet.py",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": f"timed out after {timeout}s",
                    "exit_code": None, "isolation": "--network none"}
    return {"ok": r.returncode == 0, "stdout": r.stdout[-4000:],
            "stderr": r.stderr[-2000:], "exit_code": r.returncode,
            "isolation": "--network none --cap-drop ALL --read-only"}


# --------------------------------------------------------------------------
# Deliverables
# --------------------------------------------------------------------------
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
        if s.get("body"):
            for para in str(s["body"]).split("\n\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())
        if s.get("table"):
            rows = s["table"]
            t = doc.add_table(rows=len(rows), cols=len(rows[0]))
            t.style = "Table Grid"
            for ri, row in enumerate(rows):
                for ci, cell in enumerate(row):
                    t.cell(ri, ci).text = str(cell)
                    if ri == 0:
                        for r_ in t.cell(ri, ci).paragraphs[0].runs:
                            r_.bold = True
        if s.get("citations"):
            p = doc.add_paragraph()
            r = p.add_run("Source: " + "; ".join(s["citations"]))
            r.italic = True
            r.font.size = Pt(9)

    dest = OUT / Path(filename).name
    doc.save(dest)
    return {"path": str(dest.relative_to(ROOT)), "bytes": dest.stat().st_size,
            "download": f"/api/download/{dest.name}"}


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
