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
| **Proof of no external calls** | `app/egress.py`, `egress/sentinel.sh` | see below |

## Two modes, one codebase

| | `prototype` | `sovereign` |
|---|---|---|
| Inference | NVIDIA NIM, hosted, open-weight models | local, in-network |
| Egress allowlist | 1 pinned host | **empty** |
| Network | bridge + nftables default-deny | `internal: true` — no route exists |
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

Containerised, with enforcement:

```bash
make proto      && MODE=prototype make enforce     # one host reachable
make sovereign  && MODE=sovereign  make enforce    # nothing reachable
```

## Proving the sovereign claim

The problem statement asks for proof, not a statement. Three layers, and the
app is not trusted to report on itself:

1. **Enforcement.** `egress/sentinel.sh` installs an nftables default-deny
   scoped to the workbench subnet. In sovereign mode the compose override also
   marks the network `internal: true`, so there is no default route to drop
   packets on.
2. **Observation.** `tcpdump` runs as an independent observer. If it is
   unavailable the UI reads `UNVERIFIED` and `contained: false` — it never
   shows a green badge it cannot back. Traffic that left without being on the
   allowlist is `LEAKED`, never `ALLOWED`.
3. **The tripwire.** A button that genuinely attempts `https://api.openai.com`.
   It must fail, and the failure must also appear in the captured traffic.

`make watch` runs the observer alone, for a demo split-screen.

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
