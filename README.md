# Sovereign On-Premise Agentic AI Workbench

SIH 2026 · Problem Statement **26117** · Mangalore Refinery and Petrochemicals Limited

A self-hosted agentic AI workbench for confidential industrial knowledge work.
Open-weight models only, automatic task routing across tiers, real file
deliverables, grounded in the organisation's own documents — and containment
you can watch rather than take on faith.

## What the problem statement asks for, and where it is

| Requirement | Where | State |
|---|---|---|
| Model auto-selection across ≥2 task types | `app/router.py`, `models.yaml` | six paths, L0→LV2 |
| New models addable without redesign | `models.yaml` + **Reload registry** | config edit only |
| Agentic task end to end | `app/agent.py` | scanned report → approval note |
| Coding task run and verified in a sandbox | `app/tools.py::run_python` | `--network none`, tested |
| Multimodal | `app/ocr.py`, `parse_page`, `describe_image` | scanned PDF, drawings |
| Real deliverables | `write_docx`, `write_xlsx` | Word/Excel, not chat replies |
| Local knowledge base | `app/kb.py` | chunk-level provenance |
| **Proof of no external calls** | `app/egress.py`, `egress/proxy.conf` | **enforced, measured** |

## Two modes, one codebase

| | `prototype` | `sovereign` |
|---|---|---|
| Inference | NVIDIA NIM, hosted, open-weight models | local, in-network |
| Permitted destinations | exactly 1, via the gateway | **none** — no gateway at all |
| Network | `internal: true` — no default route | `internal: true` — no default route |
| Everything else | local | local |

Knowledge base, embeddings, document store, code sandbox and file tools are
local in **both** modes. Only the model endpoint moves, and it moves by config,
because everything speaks the OpenAI protocol.

## Run it

```bash
uv venv --python 3.12 .venv && uv pip install -r requirements.txt
cp .env.example .env          # add NVIDIA_API_KEY for prototype mode
docker build -t wb-sandbox sandbox/
make sample                   # build the scanned-report fixture
make dev                      # http://127.0.0.1:8117
make test                     # every check
```

Containerised, where containment is actually enforced:

```bash
make proto        # app + gateway; one destination reachable
make sovereign    # no gateway; nothing reachable
```

## Proving the sovereign claim

The problem statement asks for proof, not a statement.

1. **Enforcement, without privileges.** The app runs on a Docker network marked
   `internal: true`, so it has no default route. The internet is not blocked
   for it; it is unreachable. A gateway container is the single deliberate
   opening — the only container on both networks, forwarding exactly one
   destination by TCP passthrough, so it never sees plaintext and never holds a
   key while certificates are still validated end to end. Removing the gateway
   (`make sovereign`) leaves no opening at all.
2. **Observation.** `tcpdump` runs as an independent observer, and enforcement
   is *detected* by reading the routing table rather than assumed. Watching
   nothing leave is not the same as nothing being able to leave, so `contained`
   requires both. If the observer is unavailable the UI reads `UNVERIFIED` — it
   never shows a green badge it cannot back. Traffic that left without being
   permitted is `LEAKED`, never `ALLOWED`.
3. **The tripwire.** A button that genuinely attempts `https://api.openai.com`.

Measured from inside the running stack:

```
no default route            api.openai.com   → does not resolve
1.1.1.1:53      unroutable  github.com       → does not resolve
tripwire        BLOCKED in 1 ms (DNS)        permitted host → 200, 81 models
```

`make watch` runs the observer alone, for a demo split-screen.

Because nothing may be fetched at runtime, the embedding model is baked into
the image at build time. A model downloaded on first use fails in an air-gapped
deployment, and it fails quietly.

## Grounding

Retrieved passages carry document, page and section. The agent must cite them,
and verification **reads the generated document back** to check the citations
that were actually written. Three failure modes are caught and escalated rather
than returned:

- an answer citing nothing when passages were retrieved
- a citation that does not resolve to a retrieved passage
- a number presented as program output that the sandbox never printed

## Layout

```
app/router.py      deterministic task router, no LLM in the hot path
app/agent.py       tool-calling loop, grounding checks, loop guards
app/tools.py       kb_search, read_document, parse_page, describe_image,
                   calculate, run_python, write_docx, write_xlsx
app/kb.py          chunking with provenance, numpy cosine retrieval
app/ocr.py         text-layer detection, then the document model
app/egress.py      containment observation and the tripwire
app/llm.py         OpenAI-protocol client; NIM, Ollama, vLLM alike
models.yaml        model registry, routing rules, per-model token budgets
egress/sentinel.sh nftables enforcement
docs/model-benchmark.md   why each model was chosen, with measurements
```

## Notes

- Model ids drift. `make verify-models` checks the registry against the live
  catalogue before a demo.
- Of 81 models the NIM catalogue lists, 11 accept completions on our key; the
  tiers were picked from what actually works, measured. See the benchmark.
- `.env` is gitignored and must stay that way.
