# Architecture

How a request moves through the system, and what each module is responsible
for. For *why* things are built the way they are, see `docs/DECISIONS.md` —
entries are referenced here as `D-n`.

---

## Deployment topology

```
                        ┌──────────────────── host ─────────────────────┐
  browser ── :8117 ──►  │  egress-gateway (nginx)                        │
                        │    ├─ http  :8117  → app:8117     (ingress)    │
                        │    └─ stream :443 → integrate.api.nvidia.com   │
                        │         ▲ the ONLY permitted destination       │
                        │         │                                      │
                        │  ── wb-internal (internal: true) ────────────  │
                        │         │     no default route exists          │
                        │  app (FastAPI, uid = host user)                │
                        │    ├─ tcpdump observer                         │
                        │    └─ docker CLI ──► sandbox (--network none)  │
                        │                                                │
                        │  data/  (bind mount: kb, uploads, out, cache,  │
                        │          audit.jsonl, users.json, secret.key)  │
                        └────────────────────────────────────────────────┘
```

- **The app has no default route** (D-7). It can reach the gateway and nothing
  else. The gateway is the only container on both networks.
- **The gateway carries both directions** — browser traffic in, one permitted
  destination out — because Docker will not publish a port from an internal
  network.
- **Sovereign mode** (`make sovereign`) removes the gateway and adds an
  in-network model server. Then nothing is reachable at all.
- **The sandbox** is launched by the app through the host's Docker daemon, as a
  sibling container with no network (D-36).

## Request lifecycle

```
POST /api/run  (prompt, attachment?, session?)          app/main.py
  │
  ├─ authenticate, check the "run" capability           app/auth.py
  ├─ load conversation history, carry the attachment    app/sessions.py
  │
  └─ Agent.run                                          app/agent.py
       │
       ├─ classify the attachment FROM THE FILE          app/ocr.py        D-30
       │     scanned PDF → page · image → drawing · digital → text
       │
       ├─ route on the whole conversation                app/router.py     D-1, D-24
       │     features → first matching rule → tier → model
       │
       ├─ L0? → parse arithmetic → calculate → done      app/tools.py      D-14
       │     (no model is ever called)
       │
       ├─ vision tier chosen? → swap loop to orchestrator                  D-5
       │     "LV2 reads · L2 reasons"
       │
       └─ _converse: the tool-calling loop (≤16 steps)
            │
            ├─ call model with tools + budget            app/llm.py        D-22
            │     retry 503/429/500 · fall back one tier
            ├─ finish_reason=length, empty? → double budget, retry
            ├─ tool calls → dedupe by signature → execute                   D-21
            │     repeats ≥2 → withdraw read-only tools
            │     repeats ≥4 → disable tools, force prose
            └─ no tool calls → answer → _verify
                  ├─ serialised tool call?        → malformed
                  ├─ sandbox runs, none succeeded → sandbox-failed          D-20
                  ├─ searched, found nothing      → ungrounded              D-19
                  ├─ fake program output?         → fabricated-output       D-18
                  ├─ read back the .docx if one was written                 D-16
                  ├─ no citations                 → uncited
                  └─ citation not retrieved       → invented-citation
       │
       ├─ verdict not ok, a tier above exists → escalate
       └─ verdict not ok, at the ceiling      → repair in place             D-23

  every step → SSE to the browser, and a line in data/audit.jsonl
```

## Modules

### `app/router.py` — which computational path
Pure function of the request text plus attachment metadata. Extracts features
(`task`, `has_image`, `image_kind`, `input_tokens`) with regexes, matches them
against the ordered rules in `models.yaml`, returns a `Decision` naming tier,
model, rule and reason. `orchestrator()` returns the strongest tool-capable
model (D-6). Tested without a network in `tests/test_router.py`.

### `models.yaml` — the registry
Every model, its tier, capabilities, token budget, and the name it resolves to
in each mode (`prototype` / `sovereign`). Routing rules and the escalation
chain. **Adding a model is an edit here and a click on Reload registry** — the
problem statement's "addable later without redesigning the system".

### `app/agent.py` — the loop and its guards
The `SYSTEM` prompt (including the six-section approval-note structure), the
conversation loop, repeat detection, budget recovery, verification and repair.
The most-changed file in the project; most entries in `DECISIONS.md` touch it.

### `app/tools.py` — what the agent can do

| Tool | Does | Notes |
|---|---|---|
| `kb_search` | hybrid retrieval with provenance | errors are errors, not empty results (D-12) |
| `read_document` | text layer, plus which pages need vision | refuses paths outside `data/` |
| `parse_page` | transcribe a scanned page | cached by content hash (D-31) |
| `describe_image` | read a drawing or photo | tiled, concurrent, degeneration-guarded (D-32, D-33) |
| `calculate` | exact arithmetic | AST whitelist, never eval (D-14) |
| `percent_change` | exact percentage change | |
| `run_python` | execute code | `--network none`, read-only, via stdin (D-36) |
| `write_docx` | Word deliverable | markdown tables become real tables; bracketed citations |
| `write_xlsx` | Excel deliverable | bold header row |

Adding one: `docs/playbooks/add-a-tool.md`.

### `app/kb.py` — retrieval
Chunks SOPs on numbered clauses and ALL-CAPS headings, keeping document, page
and section on every chunk. Embeds heading-plus-body with bge-small (ONNX, no
torch, baked into the image). Scores with BM25 and cosine similarity, both
normalised, blended at α = 0.7 (D-26, D-27). Index persisted to
`data/kb_index.npz`; built on startup if absent.

### `app/ocr.py` — deciding whether a model is needed
Checks each PDF page for a text layer and only sends pages without one to the
vision model (D-29). `classify_attachment` decides what a file is.

### `app/egress.py` — proving containment
`tcpdump` as an independent observer; enforcement detected from
`/proc/net/route` or an nftables table; the tripwire; the `LOCAL / ALLOWED /
LEAKED / BLOCKED` classification. `contained` requires all three conditions
(D-8).

### `app/llm.py` — the model client
One OpenAI-protocol client. Endpoint comes from the mode, or `MODEL_ENDPOINT`.
Retries transient errors, falls back one tier, records when it did.

### `app/auth.py` — identity
PBKDF2 passwords, HMAC-signed tokens with a per-user version (D-39), three
roles defined as capability sets:

| Role | Capabilities |
|---|---|
| engineer | run, upload, read_kb |
| approver | + approve *(not yet used — roadmap F3)* |
| admin | + manage_kb, manage_users, manage_models, read_audit |

### `app/sessions.py` — conversations
Persistent and owned: one JSON file per user in `data/conversations/`, written
atomically at 0600. Ownership is enforced in the store (D-46). Each turn keeps
what the interface needs to re-render it — answer, evidence, deliverables,
routing decision, steps and verdict. The last 12 turns are replayed to the
model as question and answer only; every turn stays visible. The title is the
first prompt, cut at a word.

### `app/audit.py` — the durable record
One JSON object per line in `data/audit.jsonl`. Readable with `grep`; no
software needed to audit it.

### `app/main.py` — HTTP surface
Routes, capability gates (`needs("...")`), SSE for the run trace and the egress
monitor.

### `static/index.html` — the interface
One file, no build step, no external resources (D-13). Sign-in gate, task
composer with attachments, conversation transcript, pipeline indicator, routing
decision, streaming trace, result with downloads, containment panel, evidence,
and Models / Knowledge / Audit / Admin tabs gated by role.

## API

All endpoints except `/api/login` and `/api/status` need `Authorization: Bearer <token>`,
sent as a header. Never put a token in a URL (D-47).

| Method | Path | Capability | Purpose |
|---|---|---|---|
| POST | `/api/login` | — | username + password → token |
| POST | `/api/logout` | signed in | revoke this token |
| GET | `/api/me` | signed in | current user and role table |
| POST | `/api/me/password` | signed in | change own password |
| GET | `/api/status` | — | mode, endpoint, models, containment |
| POST | `/api/run` | run | execute a task in a conversation; SSE stream |
| GET | `/api/conversations` | signed in | the caller's conversations, newest first |
| GET | `/api/conversations/{id}` | signed in | one conversation with every turn |
| PATCH | `/api/conversations/{id}` | signed in | rename |
| DELETE | `/api/conversations/{id}` | signed in | delete |
| POST | `/api/route` | signed in | routing decision without executing |
| POST | `/api/upload` | upload | store a file in `data/uploads` |
| GET | `/api/download/{name}` | signed in | fetch a deliverable |
| GET | `/api/files/{name}/outline` | signed in | a deliverable's title, headings, citations |
| GET | `/api/kb/documents` | read_kb | indexed documents |
| GET | `/api/kb/search` | read_kb | hybrid retrieval |
| POST | `/api/kb/build` | manage_kb | re-index |
| POST | `/api/registry/reload` | manage_models | re-read `models.yaml` |
| POST | `/api/tripwire` | signed in | attempt a forbidden call |
| GET | `/api/egress/stream` | signed in | SSE containment events |
| GET | `/api/audit` | read_audit | recent audit entries |
| GET/POST/DELETE | `/api/users…` | manage_users | account administration |


## Data on disk

| Path | What | In git |
|---|---|---|
| `data/kb/*.md` | knowledge-base source documents | yes |
| `data/uploads/` | user uploads; two demo fixtures are tracked | fixtures only |
| `data/out/` | generated deliverables | no |
| `data/cache/` | transcription cache | no |
| `data/kb_index.npz`, `kb_meta.json` | retrieval index | no — built on startup |
| `data/audit.jsonl` | audit log | no |
| `data/conversations/` | every user's conversations (0600) | **never** |
| `data/users.json` | accounts (0600) | **never** |
| `data/secret.key` | token signing key (0600) | **never** |
