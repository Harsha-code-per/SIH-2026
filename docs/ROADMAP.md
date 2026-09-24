# Roadmap

Two scopes, deliberately separated.

- **Demo scope** is what the SIH judges see at the national screening (idea
  submission deadline around **30 September 2026**). Depth over breadth: a small
  number of workflows that genuinely work end to end.
- **Finale scope** is the complete product for the Grand Finale, on the
  proposed hardware: a single workstation with an **RTX 4090 or better**.

Status marks: `[x]` done and tested · `[~]` works with known limits · `[ ]` not started.

Each item names the files it touches so an agent can start without searching.

---

## Phase 0 — Foundation `COMPLETE`

- [x] Deterministic router with a YAML model registry — `app/router.py`, `models.yaml`
- [x] Tool-calling agent loop — `app/agent.py`
- [x] OpenAI-protocol model client with retry and tier fallback — `app/llm.py`
- [x] FastAPI with server-sent-event streaming — `app/main.py`
- [x] Append-only JSONL audit log — `app/audit.py`
- [x] Test runner that cannot skip a test by position — `tests/run.py`
- [x] One-command stack — `make up`, `make down`

## Phase 1 — Demo core `COMPLETE`

Every expected-solution bullet in the problem statement has a working path.

- [x] **Model auto-selection across ≥2 task types** — six live paths, L0 through LV2
- [x] **Agentic task end to end** — scanned report → findings → approval note `.docx`
- [x] **Coding task verified in a sandbox** — `run_python`, `--network none`, tested
- [x] **Multimodal** — scanned PDF transcription and P&ID reading
- [x] **Proof of no external calls** — no default route, tripwire, independent observer
- [x] **Local knowledge base** — hybrid BM25 + dense retrieval with provenance
- [x] **Word and Excel deliverables** — `write_docx`, `write_xlsx`

## Phase 2 — Demo hardening `COMPLETE`

Found by running the demo rather than reading the code.

- [x] Page-transcription cache: 48s → 0s on repeat — `app/tools.py::parse_page`
- [x] Hybrid retrieval: identifier queries went from six searches to one — `app/kb.py`
- [x] Tiled drawing reading: 365s → 12s — `app/tools.py::describe_image`
- [x] Degenerate-output detection for vision models — `_looks_degenerate`
- [x] Multi-turn conversations — `app/sessions.py`
- [x] Accounts, roles, admin panel — `app/auth.py`
- [x] Working file upload in the UI (the control was dead) — `static/index.html`
- [x] Routing engineering questions to L2: 155s → 6s — `app/router.py`

---

## Phase 2b — Interface redesign `IN PROGRESS`

Rebuilding the interface in the shape of Claude, ChatGPT and Gemini — history
sidebar, conversation in the centre, reasoning in a right-hand Inspector — with
shadcn/ui and prompt-kit on Vite. Findings from studying the three live are in
`docs/ui/REFERENCE.md`.

- [x] **A. Backend** — owned, persistent conversations; scoped and gated API;
  SPA fallback; deliverable outline; no tokens in URLs
- [x] **B. Scaffold** — `web/` with Vite, Tailwind v4, shadcn, prompt-kit; warm
  neutral tokens for both themes; multi-stage build; bundled fonts
- [x] **C. Shell** — sign-in; sidebar with history grouped by age, search,
  rename, delete, admin group, containment indicator and account menu; thread
  with markdown answers and a one-line activity summary; composer with
  attachments, drag and drop, and a live routing preview; the Inspector with
  Activity, Sources, Files and Shield; a working Settings dialog
- [x] **D. AI rendering** — citations as inline pills that preview the clause
  on hover and pin it in the Inspector on click; passages rendered as markdown;
  a verification seal built only from checks the backend ran; the routing chip
  with its reason; deliverables as file cards with an outline and Download
- [x] **E. Views** — Knowledge (documents, passage search, rebuild), Users
  (add, role, remove), Models (tiers and routing rules, reload), Audit (filtered
  log); ⌘K palette; `/` task templates in the composer; an error boundary so a
  failing view no longer blanks the page
- [x] **F. Verify** — phone width (the Inspector no longer covers the
  conversation), both themes (native controls follow the app theme), unnamed
  controls swept, zero requests to any host but the workbench on every view,
  demo playbook click paths rewritten, clean clone builds and passes
- [ ] **G. Streaming** — token and thinking streams, visible revision on repair

**Transitional state:** Knowledge, Users, Models and Audit are placeholder
pages until phase E; citations render as raw `[Doc.md#7]` until phase D.

## Phase 3 — Demo completion `IN PROGRESS · due 30 Sept`

What still stands between the current build and a submission.

### 3.1 PowerPoint deliverable `[ ]` — **PS gap, do first**
The problem statement lists "approval notes, **PPT**/Word/Excel files".
`python-pptx` is already installed; there is no tool.
- Add `write_pptx(title, slides: [{title, bullets, table?, notes?}], filename)` to
  `app/tools.py`, registered in `TOOLS`. Follow `docs/playbooks/add-a-tool.md`.
- Same citation rules as `write_docx`; teach `_docx_text` an equivalent reader
  for `.pptx` so verification can check what was written.
- Test in `tests/test_deliverables.py`.

### 3.2 Consistent approval-note structure `[~]`
Notes are correct and cited, but the model sometimes omits section headings, so
a note occasionally reads as flat paragraphs.
- Validate in `write_docx`: if the request is an approval note, require the six
  sections named in `app/agent.py::SYSTEM`, and return an error naming the
  missing ones so the loop repairs it.

### 3.3 Handwritten notes `[ ]` — **PS names this explicitly**
- A handwriting fixture in `scripts/` (render text with a handwriting-style
  font plus jitter, same approach as `make_scanned_sample.py`).
- Measure transcription accuracy and record it in `docs/model-benchmark.md`.

### 3.4 Presentation and video `[ ]` — **submission artifacts**
- 6-slide PPT in the SIH format. Content outline in `docs/PROBLEM-STATEMENT.md`.
- Demo video, team-narrated (SIH rules forbid AI-generated narration). Script
  and timings in `docs/playbooks/run-the-demo.md`.

### 3.5 Clean-machine verification `[x]`
Fresh clone from GitHub, `make up`, full coding task, containment proved. Re-run
before submitting: `docs/playbooks/run-the-demo.md` has the checklist.

---

## Phase F — Finale scope

The full build for the proposed RTX 4090-class workstation. Ordered by
dependency, not importance.

### F1. Local inference `[ ]` — **the headline migration**
The architecture makes this a configuration change. See `docs/playbooks/go-local.md`.
- Serve models locally (Ollama for simplicity, vLLM for throughput).
- Fill in the `sovereign:` column of `models.yaml` with real local model names.
- `make sovereign` removes the gateway entirely: nothing is reachable.
- **Budget a day for retuning.** A local model follows tool-calling
  instructions less reliably than the hosted 120B. The loop guards in
  `app/agent.py` exist for exactly this and have only been exercised against
  the large model so far.

Suggested local models for 24GB VRAM (verify availability at build time):

| Tier | Suggested | Approx VRAM |
|---|---|---|
| L1 | Qwen3-8B or Gemma-4 E4B | 5–6 GB |
| L2 | Qwen3-32B Q4, or gpt-oss-20b | 16–20 GB |
| LV | GLM-OCR 0.9B or PaddleOCR-VL | 2–3 GB |
| LV2 | Qwen2.5-VL-7B | 6–8 GB |
| Embeddings | bge-small (already local) | <1 GB |

Tiers load on demand; not all need to be resident at once.

### F2. Re-benchmark on target hardware `[ ]`
Hosted latency inverted the tier ordering (the cheap tier was four times
slower). On local hardware it should not. Re-run the measurements in
`docs/model-benchmark.md` and retune `DEFAULT_ALPHA` in `app/kb.py` if the
embedding model changes.

### F3. Approval workflow `[ ]`
The `approver` role and its `approve` capability exist in `app/auth.py` but no
endpoint uses them. A note is drafted, then submitted, then approved or
returned, with every transition in the audit log.
- `app/main.py`: `POST /api/notes/{id}/submit`, `/approve`, `/return`
- A notes store (JSON is fine at this scale)
- Routing per SOP §7.2: Zone D findings need two signatures

### F4. Knowledge-base management `[ ]`
Documents currently go in `data/kb/` by hand. Admins should upload, list,
remove and re-index from the interface.
- Endpoints gated on `manage_kb`; the capability already exists.
- Per-document chunk counts and last-indexed time in the Knowledge tab.

### F5. Photographs `[ ]`
The problem statement names photographs alongside drawings. `describe_image`
handles image files, but no photograph fixture or accuracy measurement exists.

### F6. Persistent conversation history `[x]`
Done early as phase A of the interface redesign: owned, persisted per user,
scoped in the store (D-46).

### F7. Streaming model output `[ ]`
Steps stream today; the final answer arrives whole. Token streaming makes the
interface feel like the tools the problem statement compares against.

### F8. Evaluation harness `[ ]`
The retrieval and drawing evaluations are small hand-built sets. A proper
harness: a question bank with expected answers and citations, run nightly,
reporting accuracy per tier. This is also what makes F1 retuning measurable.

### F9. Concurrency and scale `[ ]`
One workstation, a few users. If it grows:
- Retrieval moves from in-memory numpy to `sqlite-vec` past ~50k chunks
  (marked with a `ponytail:` comment in `app/kb.py`).
- A reranker stage after hybrid retrieval.
- vLLM batching for concurrent users.

### F10. Enterprise identity `[ ]`
Local accounts are deliberate for a single workstation. A refinery deployment
federates against its own directory (LDAP / Active Directory / SAML). Keep the
capability model in `app/auth.py`; replace only where identity comes from.

### F11. Audit hardening `[ ]`
The audit log is append-only by convention, not by construction. Hash-chaining
each entry to the previous one makes tampering detectable. Export to the
organisation's log retention.

### F12. Integrations `[ ]` — **explicitly out of scope until asked**
SAP, e-Office and similar. Not requested by the problem statement. Do not build
speculatively.

---

## Known limitations, stated plainly

Put these on a slide rather than have a judge find them.

- **Inference is hosted today.** Open-weight models on NVIDIA NIM, reached
  through a gateway that permits exactly one destination. F1 removes it.
- **Drawing reading is imperfect.** 7 of 9 tags and 3 of 3 line numbers on the
  test sheet. Misses are function-letter confusions inside instrument bubbles
  (`FIC-2043` read as `FI-2043`). The interface shows extracted tags so an
  engineer checks them.
- **The cheap tier is slow on the hosted endpoint** — 15s against 3.7s for the
  strong tier. A property of shared scheduling, not the models.
- **Free-tier NIM is rate-limited and occasionally returns 503.** The client
  retries and falls back a tier; a run can still be slow under load.
- **Only 11 of the 81 catalogued NIM models accept completions on our key.**
  `make verify-models` checks the registry before a demo.
