# Playbook: add documents to the knowledge base

## Supported formats

`.md`, `.txt` and `.pdf` in `data/kb/`. PDFs with a text layer are read
directly; scanned PDFs need their text layer first (roadmap F4 adds upload and
transcription from the interface).

## 1. Write for the chunker

The chunker splits on **numbered clauses** (`4.2`, `7.1.3`) and **ALL-CAPS
headings**. That is how SOPs are written, and it is what lets a citation point
at a clause rather than a page.

```
4. VIBRATION ACCEPTANCE CRITERIA

4.2 For Group 1 machines (rated above 15 kW, rigid foundation) the following
zone boundaries apply to overall RMS velocity:
```

Put identifiers — clause numbers, equipment tags, standard numbers — **in the
heading line**. Headings are indexed with extra weight, and identifier queries
depend on it (D-26).

## 2. Add and re-index

```bash
cp new-procedure.md data/kb/
```

Then **Rebuild index** in the Knowledge tab (admin), or delete
`data/kb_index.npz` and restart — it rebuilds on startup.

## 3. Check retrieval finds it

```bash
TOKEN=...   # from /api/login
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8117/api/kb/search?q=clause+4.2&k=3"
```

For anything important, add a case to `tests/test_retrieval.py::CASES` — the
query an engineer would type, and a string that must appear in a retrieved
chunk. The suite asserts every case is found within the top five.

## Do not

- Commit real MRPL documents. The dataset guidance is public samples only, and
  this repository is public.
- Put secrets in documents. `data/kb/` is committed.
