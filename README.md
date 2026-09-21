# Sovereign On-Premise Agentic AI Workbench

SIH 2026 &middot; Problem Statement **26117** &middot; Mangalore Refinery and Petrochemicals Limited

A self-hosted agentic AI workbench for confidential industrial knowledge work.
Open-weight models only, multi-model with automatic task routing, real file
deliverables, grounded in a local knowledge base &mdash; and containment you can
watch rather than take on faith.

## Two modes, one codebase

| | `prototype` | `sovereign` |
|---|---|---|
| Inference | NVIDIA NIM, hosted | local, in-network |
| Egress allowlist | 1 pinned host | **empty** |
| Network | bridge + nftables default-deny | `internal: true` &mdash; no route exists |
| Everything else | local | local |

The knowledge base, embeddings, document store, code sandbox and file tools are
local in **both** modes. Only the model endpoint moves, and it moves by config.

## Run it

```bash
uv venv --python 3.12 .venv && uv pip install -r requirements.txt
make dev                      # http://127.0.0.1:8117
make test                     # router truth table + sovereignty checks
```

Containerised, with enforcement:

```bash
make proto      && MODE=prototype make enforce     # one host reachable
make sovereign  && MODE=sovereign  make enforce    # nothing reachable
```

## Proving the sovereign claim

The problem statement asks for proof, not a statement &mdash; so there are three
independent layers, and the app is not trusted to report on itself:

1. **Enforcement.** `egress/sentinel.sh` installs an nftables default-deny scoped
   to the workbench subnet. In sovereign mode the compose override also marks the
   network `internal: true`, so there is no default route to drop packets on.
2. **Observation.** `tcpdump` runs as an independent observer and reports what
   actually crossed the wire. If it is unavailable the UI reads
   `UNVERIFIED` &mdash; it never shows a green badge it cannot back.
3. **The tripwire.** A button that genuinely attempts `https://api.openai.com`.
   It must fail, and the failure must also appear in the captured traffic.

`make watch` gives you the observer on its own for a demo split-screen.

## Adding a model

Edit `models.yaml`, then hit **Reload registry**. No code changes &mdash; that is
the PS requirement that new open-weight models be addable without redesigning
the system.

## Layout

```
app/router.py     deterministic task router (no LLM in the hot path)
app/egress.py     containment observation + tripwire
app/main.py       API + SSE
models.yaml       model registry and routing rules
egress/sentinel.sh  nftables enforcement
tests/            router truth table, sovereignty checks
```
