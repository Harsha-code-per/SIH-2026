# Sovereign AI Workbench

**Smart India Hackathon 2026 · Problem Statement 26117 · Mangalore Refinery and
Petrochemicals Limited**

A self-hosted agentic AI workbench for confidential industrial knowledge work.
It reads scanned inspection reports and engineering drawings, checks findings
against the organisation's own SOPs, and produces approval notes, spreadsheets
and verified code — with every claim cited and **nothing leaving the premises,
proven rather than promised**.

```bash
make up          # then open http://127.0.0.1:8117
```

---

## What it does

- **Routes each task to the right model** — arithmetic to a calculator with no
  model at all, quick questions to a small model, analysis to a large one,
  scans and drawings to vision models. Deterministic and explainable.
- **Works as an agent** — plans, calls local tools, checks its own output, and
  repairs it instead of answering once.
- **Reads what engineers actually have** — scanned PDFs with no text layer, and
  P&IDs.
- **Produces real deliverables** — Word approval notes with a fixed six-section
  structure, Excel registers, code that ran in a sandbox.
- **Cites everything** — hybrid retrieval over local SOPs, and verification
  reads the generated document back to confirm every citation resolves.
- **Proves containment** — the app has no route to the internet. A tripwire
  deliberately calls OpenAI on camera and is blocked in a millisecond.

## Measured, not claimed

| | |
|---|---|
| "What zone is 8.2 mm/s?" — retrieved, compared, cited | **6 s** |
| Scanned page transcription | **48 s** first time · **0 s** cached |
| Engineering drawing, tiled and concurrent | **12 s** |
| Tripwire to `api.openai.com` | **blocked in ~1 ms**, at DNS |
| Automated tests | **131 passing** |

## Documentation

**Starting work on this project — human or AI agent? Read [`AGENTS.md`](AGENTS.md).**

| | |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Start here. Context, rules, where things are |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Demo scope vs finale scope, with status |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How a request flows; every module; the API |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Why things are the way they are — read before changing them |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Running, configuring, troubleshooting |
| [`docs/PROBLEM-STATEMENT.md`](docs/PROBLEM-STATEMENT.md) | PS 26117, mapped requirement by requirement to code |
| [`docs/model-benchmark.md`](docs/model-benchmark.md) | Why each model was chosen, with measurements |
| [`docs/playbooks/`](docs/playbooks/) | Step-by-step recipes for common tasks |

## Honest status

Demo-ready. Every expected-solution bullet in the problem statement has a
working, tested path.

Inference currently uses **hosted open-weight models** on NVIDIA NIM, reached
through a gateway that permits exactly one destination. Moving it on-premise is
a configuration change — [`docs/playbooks/go-local.md`](docs/playbooks/go-local.md).
The full list of limitations is in [`docs/ROADMAP.md`](docs/ROADMAP.md), and it
belongs on a slide rather than in a judge's question.

## Requirements

Docker with Compose v2, and an NVIDIA NIM API key from
<https://build.nvidia.com>. Nothing else — the stack is containerised.
