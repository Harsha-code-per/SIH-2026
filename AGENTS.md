# AGENTS.md — start here

Context for any AI coding agent or developer picking this project up. Written
to be tool-agnostic: Claude Code, Cursor, Copilot, Aider, Codex, Windsurf or a
human all need the same facts.

**Read this file first, then `docs/ROADMAP.md` to see what is next.**

---

## What this is

A **Sovereign On-Premise Agentic AI Workbench** for Smart India Hackathon 2026,
problem statement **26117**, posed by Mangalore Refinery and Petrochemicals
Limited (MRPL).

Refineries generate sensitive knowledge work — approval notes, inspection
reports, P&IDs, engineering calculations — that cannot go to cloud AI because
the data is confidential. This is a self-hosted assistant that does that work
without anything leaving the premises, and **proves** it rather than claiming
it.

The full problem statement and a requirement-by-requirement mapping to code is
in `docs/PROBLEM-STATEMENT.md`.

## The one-paragraph technical summary

A FastAPI backend serves a single-page interface. A **deterministic router**
reads the request and picks a computational tier (L0 arithmetic with no model,
L1 cheap text, L2 reasoning, LV document vision, LV2 drawing vision) from a
YAML registry. An **agent loop** drives a tool-calling conversation with nine
local tools: hybrid RAG search, document reading, page transcription, drawing
reading, exact arithmetic, sandboxed Python, and Word/Excel writers. Every
factual claim must cite a retrieved passage, and **verification reads the
generated document back** to check. The whole stack runs in Docker on a network
with **no default route**, so reaching the internet is not blocked, it is
unroutable.

## Run it

```bash
git clone <repo> && cd SIH-2026
make up          # builds and starts everything; creates .env if missing
```

Put an `NVIDIA_API_KEY` in `.env`, then `make restart`. Open
<http://127.0.0.1:8117>. Sign in with the admin account — the password is
printed in `make logs` on first run, or set `ADMIN_PASSWORD` in `.env`.

`make` alone lists every command. Full operational detail is in
`docs/OPERATIONS.md`.

## Where things are

```
app/router.py      deterministic tier routing; no model in the hot path
app/agent.py       the tool-calling loop, grounding checks, loop guards
app/tools.py       the nine tools the agent can call
app/kb.py          chunking, hybrid BM25 + dense retrieval, provenance
app/ocr.py         text-layer detection, then the document model
app/egress.py      containment observation and the tripwire
app/auth.py        users, roles, signed tokens
app/sessions.py    multi-turn conversation state
app/llm.py         OpenAI-protocol client; NIM, Ollama, vLLM alike
app/main.py        HTTP API and SSE streaming
static/index.html  the whole interface, one file, zero external resources
models.yaml        model registry and routing rules — config, not code
egress/proxy.conf  the controlled-egress gateway
tests/run.py       the test runner; `make test`
docs/              architecture, roadmap, decisions, operations, playbooks
```

## Rules this codebase holds itself to

These are not style preferences. Each one exists because breaking it caused a
real bug that is written up in `docs/DECISIONS.md`.

1. **Never claim containment you cannot demonstrate.** `contained` requires an
   observer running *and* enforcement detected *and* zero leaks. Watching
   nothing leave is not the same as nothing being able to leave.
2. **A wrong number is worse than no number.** Arithmetic goes through the
   `calculate` tool, never the model. Output the model presents as program
   output is checked against what the sandbox actually printed.
3. **A claim without a resolvable citation fails verification.** Verification
   reads the generated `.docx` back rather than trusting the chat reply.
4. **Config over code.** Adding a model is an edit to `models.yaml`. If a change
   needs new code to add a model, the change is wrong.
5. **Ship the models, never fetch at runtime.** The embedding model is baked
   into the image at build time. Anything downloaded on first use fails in an
   air-gapped deployment, and fails quietly.
6. **Every non-trivial behaviour has a runnable test.** 101 currently, via
   `make test`. Tests are collected by `tests/run.py`, never by a `__main__`
   block — see decision D-41 in `docs/DECISIONS.md` for why.
7. **The interface loads zero external resources.** No CDN, no Google Fonts. An
   air-gapped workbench that fetches a stylesheet undermines its own claim.

## What is real and what is not

Be precise about this when writing slides, documentation or commit messages.
The project's main asset is that its claims are true.

| Claim | Status |
|---|---|
| No default route from the app container | **Real**, measured, tested |
| Tripwire to `api.openai.com` blocked | **Real**, ~1ms, blocked at DNS |
| Code sandbox has no network | **Real**, tested |
| Local knowledge base with citations | **Real** |
| Deterministic tier routing | **Real** |
| Word / Excel deliverables | **Real** |
| Scanned document reading | **Real** |
| Drawing reading | **Real**, with known accuracy limits (see benchmark) |
| Runs entirely on-premise today | **Not yet.** Inference is hosted open-weight models via NVIDIA NIM. One config change away — see `docs/ROADMAP.md` phase F1 |
| SAP / e-Office integration | **Not built.** Not in scope |
| Enterprise SSO | **Not built.** Local accounts only, deliberately |

## Current phase

**Demo-ready, pre-finale.** The five demo-critical work items are complete. The
next block of work is in `docs/ROADMAP.md`, which distinguishes *demo scope*
(what the judges see) from *finale scope* (the full build).

## Working agreements

- **Commit and push regularly**, at each meaningful checkpoint. The GitHub repo
  is the submission artifact, so uncommitted work is missing work.
- **Never commit secrets.** `.env` is gitignored. Check any diff for `nvapi-`
  before committing.
- **Run `make test` before committing.** It is fast and it catches real things.
- **Verify by running, not by reading.** Most bugs in `docs/DECISIONS.md` were
  invisible in the source and obvious the moment something was executed.
- **Write down why, not just what.** If you discover something the hard way,
  add it to `docs/DECISIONS.md` so the next agent does not rediscover it.

## Playbooks

Step-by-step recipes for common tasks, in `docs/playbooks/`:

- `add-a-model.md` — put a new open-weight model behind a tier
- `add-a-tool.md` — give the agent a new capability
- `add-knowledge.md` — add documents to the knowledge base
- `verify-containment.md` — prove the sovereignty claim
- `run-the-demo.md` — the demo script, in order, with expected timings
- `go-local.md` — switch inference to local models (the finale migration)
