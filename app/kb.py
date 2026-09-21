"""Local knowledge base.

Chunks carry their origin -- document, page, section -- because a finding in an
approval note is worthless to an inspection engineer if it cannot be traced back
to the page it came from. Retrieval returns provenance, not just text.

No vector database. A few hundred chunks is a numpy dot product; a service that
needs its own container would be more moving parts than the problem has.
ponytail: in-memory cosine, O(n) per query. Swap to sqlite-vec past ~50k chunks.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "kb"
INDEX = ROOT / "data" / "kb_index.npz"
META = ROOT / "data" / "kb_meta.json"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # 133MB ONNX, no torch


@dataclass
class Chunk:
    id: str
    text: str
    doc: str
    page: int | None = None
    section: str | None = None

    def cite(self) -> str:
        bits = [self.doc]
        if self.page is not None:
            bits.append(f"p.{self.page}")
        if self.section:
            bits.append(self.section)
        return " · ".join(bits)

    def as_dict(self) -> dict:
        return asdict(self) | {"cite": self.cite()}


_SECTION = re.compile(r"^\s{0,3}(?:#{1,4}\s*)?((?:\d+\.)+\d*|[A-Z][A-Z \-]{4,})\s*(.*)$")


def split_sections(text: str) -> list[tuple[str | None, str]]:
    """Split on numbered clauses (4.2) or ALL-CAPS headings -- how SOPs are written."""
    out: list[tuple[str | None, str]] = []
    current, buf = None, []
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m and len(line.strip()) < 90:
            if buf:
                out.append((current, "\n".join(buf).strip()))
            current = f"§{m.group(1).strip()}" + (f" {m.group(2).strip()}" if m.group(2) else "")
            buf = []
        else:
            buf.append(line)
    if buf:
        out.append((current, "\n".join(buf).strip()))
    return [(s, t) for s, t in out if t]


def window(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Paragraph-aware windows. Keeps a table or clause intact where it can."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            buf = (buf[-overlap:] + "\n\n" + p) if buf and len(p) < size else p
            while len(buf) > size:
                chunks.append(buf[:size])
                buf = buf[size - overlap:]
    if buf:
        chunks.append(buf)
    return chunks


class KnowledgeBase:
    def __init__(self, embed_model: str = EMBED_MODEL):
        self._embedder = None
        self._embed_model = embed_model
        self.chunks: list[Chunk] = []
        self.vectors: np.ndarray | None = None

    @property
    def embedder(self):
        # Imported lazily: loading the ONNX model costs a second we should only
        # pay when something is actually indexed or queried.
        if self._embedder is None:
            from fastembed import TextEmbedding
            self._embedder = TextEmbedding(model_name=self._embed_model)
        return self._embedder

    def embed(self, texts: list[str]) -> np.ndarray:
        v = np.array(list(self.embedder.embed(texts)), dtype=np.float32)
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

    # -- indexing -----------------------------------------------------------
    def add_text(self, text: str, doc: str, page: int | None = None) -> int:
        n = 0
        for section, body in split_sections(text) or [(None, text)]:
            for part in window(body):
                self.chunks.append(Chunk(
                    id=f"{doc}#{len(self.chunks)}", text=part,
                    doc=doc, page=page, section=section))
                n += 1
        return n

    def ingest_file(self, path: Path) -> int:
        """Text and markdown go straight in; PDFs go through the reader."""
        if path.suffix.lower() == ".pdf":
            from .ocr import read_pdf
            return sum(self.add_text(pg.text, path.name, pg.page)
                       for pg in read_pdf(path) if pg.text.strip())
        return self.add_text(path.read_text(errors="replace"), path.name)

    def build(self, kb_dir: Path = KB_DIR) -> dict:
        self.chunks, self.vectors = [], None
        files = sorted(p for p in kb_dir.rglob("*")
                       if p.is_file() and p.suffix.lower() in {".txt", ".md", ".pdf"})
        per = {p.name: self.ingest_file(p) for p in files}
        if self.chunks:
            self.vectors = self.embed([c.text for c in self.chunks])
            np.savez_compressed(INDEX, vectors=self.vectors)
            META.write_text(json.dumps([asdict(c) for c in self.chunks]))
        return {"documents": len(files), "chunks": len(self.chunks), "per_document": per}

    def load(self) -> bool:
        if not (INDEX.exists() and META.exists()):
            return False
        self.chunks = [Chunk(**d) for d in json.loads(META.read_text())]
        self.vectors = np.load(INDEX)["vectors"]
        return True

    # -- retrieval ----------------------------------------------------------
    def search(self, query: str, k: int = 6) -> list[dict]:
        if self.vectors is None or not self.chunks:
            return []
        sims = self.vectors @ self.embed([query])[0]
        k = min(k, len(self.chunks))
        idx = np.argpartition(-sims, k - 1)[:k]
        idx = idx[np.argsort(-sims[idx])]
        return [self.chunks[i].as_dict() | {"score": round(float(sims[i]), 4)}
                for i in idx]


KB = KnowledgeBase()
