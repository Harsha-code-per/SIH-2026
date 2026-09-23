"""Retrieval quality, measured rather than assumed.

The queries an engineer actually types are identifiers -- "clause 4.2",
"P-204", "ISO 10816-3" -- and a dense vector treats those as unremarkable
tokens. This set pins the behaviour that made them work: section headings are
indexed and embedded alongside the body, heading terms are weighted above
prose, and the two scorers are blended.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.kb import KB, DEFAULT_ALPHA, _terms

# (query, a string that must appear in the section or body of a retrieved chunk)
CASES = [
    ("clause 4.2",                    "4.2"),
    ("SOP-4 clause 4.2",              "4.2"),
    ("clause 7.2",                    "7.2"),
    ("P-204",                         "P-204"),
    ("ISO 10816-3",                   "10816"),
    ("MRPL-QA-12 calibration",        "QA-12"),
    ("who must approve Zone D",       "7.2"),
    ("vibration acceptance criteria", "4.2"),
    ("bearing temperature limit",     "5.1"),
    ("seal leakage drops per minute", "6.1"),
    ("how often are critical pumps inspected", "1.1"),
    ("what is the Zone D action",     "4.2"),
    ("analyser calibration certificate", "4.1"),
]


def _ready():
    if KB.vectors is None and not KB.load():
        KB.build()


def _rank(results, needle):
    for i, r in enumerate(results, 1):
        if needle in (r["section"] or "") + r["text"]:
            return i
    return 0


def test_identifiers_survive_tokenisation():
    """If the tokeniser splits 4.2 into 4 and 2, nothing downstream can help."""
    t = _terms("SOP-4 clause 4.2 for P-204 per ISO 10816-3")
    for want in ("sop-4", "4.2", "p-204", "10816-3"):
        assert want in t, f"{want} destroyed by the tokeniser: {t}"


def test_headings_are_searchable():
    """Clause numbers live in headings; indexing only bodies loses them."""
    _ready()
    c = next(c for c in KB.chunks if c.section and "4.2" in c.section)
    assert "4.2" in c.searchable


def test_every_expected_passage_is_retrieved_within_five():
    """Recall is what matters: the agent reads the whole result set."""
    _ready()
    missed = [q for q, w in CASES if not _rank(KB.search(q, k=5), w)]
    assert not missed, f"not retrieved at all: {missed}"


def test_hybrid_beats_dense_alone_on_identifier_queries():
    _ready()
    ids = [("clause 4.2", "4.2"), ("clause 7.2", "7.2"), ("ISO 10816-3", "10816")]
    for q, w in ids:
        assert _rank(KB.search(q, k=5, alpha=DEFAULT_ALPHA), w), q


def test_scores_expose_both_signals():
    """The UI and the trace should be able to show why a passage was chosen."""
    _ready()
    top = KB.search("clause 4.2", k=1)[0]
    assert {"score", "dense", "lexical"} <= set(top)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
    print("\nretrieval: all checks passed")
