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
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "kb"
INDEX = ROOT / "data" / "kb_index.npz"
META = ROOT / "data" / "kb_meta.json"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # 133MB ONNX, no torch
BM25_K1, BM25_B = 1.5, 0.75              # standard Okapi parameters

# A term in a section heading counts for more than the same term in prose.
# "clause 4.2" should return clause 4.2, not the later clause that happens to
# mention it -- the heading says what a passage *is*, the body only what it
# talks about.
HEADING_BOOST = 4

# How much weight the dense side carries. Tuned on the query set in
# tests/test_retrieval.py: 0.7 is the only value that retrieves every expected
# passage within the top five. Lexical-heavy settings win slightly more
# first places but drop a passage entirely, and for an agent that reads the
# whole result set a missing passage costs far more than a lower rank.
DEFAULT_ALPHA = 0.7

# Tokens worth matching exactly. Keeping dots and hyphens inside a token is the
# point: "4.2" must not become "4" and "2", and "P-204" must not become "p" and
# "204", or the identifiers an engineer searches by are destroyed by the
# tokeniser before scoring ever happens.
_TERM = re.compile(r"[a-z]+(?:[-.][a-z0-9]+)*|\d+(?:\.\d+)+|[a-z]*\d[\w-]*", re.I)


def _terms(text: str) -> list[str]:
    return [t.lower() for t in _TERM.findall(text)]


@dataclass
class Chunk:
    id: str
    text: str
    doc: str
    page: int | None = None
    section: str | None = None

    @property
    def searchable(self) -> str:
        """Heading plus body.

        The clause number lives in the heading -- "4.2", "ISO 10816-3",
        "MRPL-QA-12" -- while the requirement lives in the body. Indexing only
        the body meant the identifiers an engineer searches by were absent from
        the index entirely, which no amount of scoring can recover from.
        """
        return f"{self.section} {self.doc}\n{self.text}" if self.section else \
               f"{self.doc}\n{self.text}"

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
            title = m.group(2).strip()
            # Keep the citation label short enough to read in a table cell.
            if len(title) > 55:
                title = title[:52].rsplit(" ", 1)[0] + "…"
            current = f"§{m.group(1).strip()}" + (f" {title}" if title else "")
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
        self.df: dict[str, int] | None = None      # term -> document frequency
        self.tf_matrix: dict[str, list] = {}       # term -> [(chunk index, count)]
        self.lengths: np.ndarray | None = None
        self.avg_len: float = 1.0

    def _index_terms(self) -> None:
        """Build the lexical index. Pure counting, no model, milliseconds."""
        from collections import Counter
        self.df, self.tf_matrix = {}, {}
        lengths = []
        for i, c in enumerate(self.chunks):
            counts = Counter(_terms(c.text))
            body_len = sum(counts.values()) or 1
            if c.section:
                for t in _terms(c.section):
                    counts[t] += HEADING_BOOST
            counts[c.doc.lower()] += 1
            # Length normalisation uses the body only, so boosting a heading
            # does not make the passage look longer and penalise itself.
            lengths.append(body_len)
            for term, n in counts.items():
                self.df[term] = self.df.get(term, 0) + 1
                self.tf_matrix.setdefault(term, []).append((i, n))
        self.lengths = np.array(lengths, dtype=np.float32)
        self.avg_len = float(self.lengths.mean()) if len(lengths) else 1.0

    @property
    def embedder(self):
        # Imported lazily: loading the ONNX model costs a second we should only
        # pay when something is actually indexed or queried.
        if self._embedder is None:
            from fastembed import TextEmbedding
            # cache_dir is where the image baked the weights. Without it
            # fastembed reaches for HuggingFace, which cannot work air-gapped.
            self._embedder = TextEmbedding(
                model_name=self._embed_model,
                cache_dir=os.environ.get("FASTEMBED_CACHE_PATH") or None)
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
            self.vectors = self.embed([c.searchable for c in self.chunks])
            self._index_terms()
            np.savez_compressed(INDEX, vectors=self.vectors)
            META.write_text(json.dumps([asdict(c) for c in self.chunks]))
        return {"documents": len(files), "chunks": len(self.chunks), "per_document": per}

    def load(self) -> bool:
        if not (INDEX.exists() and META.exists()):
            return False
        self.chunks = [Chunk(**d) for d in json.loads(META.read_text())]
        self.vectors = np.load(INDEX)["vectors"]
        self._index_terms()      # cheap enough to rebuild rather than persist
        return True

    # -- retrieval ----------------------------------------------------------
    def _bm25(self, query: str) -> np.ndarray:
        """Okapi BM25 over the chunk corpus.

        Embeddings are good at meaning and bad at identifiers. "clause 4.2",
        "P-204" and "ISO 10816-3" are exactly what an engineer types, and a
        dense vector treats them as unremarkable tokens -- the agent was
        visibly flailing on "clause 4.2" while the passage sat in the index.
        Lexical scoring finds a rare token immediately.
        """
        q = _terms(query)
        if not q or self.df is None:
            return np.zeros(len(self.chunks), dtype=np.float32)
        n = len(self.chunks)
        scores = np.zeros(n, dtype=np.float32)
        for term in q:
            df = self.df.get(term, 0)
            if not df:
                continue
            # Rare terms carry most of the signal, which is the whole point here.
            idf = np.log(1 + (n - df + 0.5) / (df + 0.5))
            tf = self.tf_matrix.get(term)
            if tf is None:
                continue
            for i, f in tf:
                norm = f * (BM25_K1 + 1) / (
                    f + BM25_K1 * (1 - BM25_B + BM25_B * self.lengths[i] / self.avg_len))
                scores[i] += idf * norm
        return scores

    @staticmethod
    def _normalise(a: np.ndarray) -> np.ndarray:
        """Map to 0..1 so two different scoring scales can be mixed."""
        lo, hi = float(a.min()), float(a.max())
        return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)

    def search(self, query: str, k: int = 6, alpha: float = DEFAULT_ALPHA) -> list[dict]:
        """Hybrid retrieval: dense similarity blended with BM25.

        alpha weights the dense side; 0.5 is an even blend. Both are normalised
        first because cosine similarity and BM25 do not share a scale.
        """
        if self.vectors is None or not self.chunks:
            return []
        dense = self.vectors @ self.embed([query])[0]
        lexical = self._bm25(query)
        combined = (alpha * self._normalise(dense)
                    + (1 - alpha) * self._normalise(lexical))
        k = min(k, len(self.chunks))
        idx = np.argpartition(-combined, k - 1)[:k]
        idx = idx[np.argsort(-combined[idx])]
        return [self.chunks[i].as_dict() | {
                    "score": round(float(combined[i]), 4),
                    "dense": round(float(dense[i]), 4),
                    "lexical": round(float(lexical[i]), 4)}
                for i in idx]


KB = KnowledgeBase()
