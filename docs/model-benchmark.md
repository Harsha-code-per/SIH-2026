# Model selection evidence

Measured on the NVIDIA NIM hosted endpoint, 2026-09-21. Identical prompt with a
`kb_search` tool definition attached; 3 runs each; 70s ceiling.

| Model | median | runs | tool calls | verdict |
|---|---|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | **1.7s** | 1.2 / 1.7 / 2.0 | yes | **L2** |
| `meta/muse-glimmer-30b` | 3.8s | 2.6 / 3.8 / 13.6 | **no** | rejected |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | **13.5s** | 13.5 / 8.8 / 36.1 | yes | **L1** |
| `openai/gpt-oss-20b` | >70s | timeout ×3 | — | rejected |

## Why these two

Both selected models are Nemotron-3, differing in active parameters per token
(3B vs 12B). That is what a tier is meant to express: the same capability
surface at different compute cost. Pairing models from one family also keeps
prompt behaviour consistent when the router escalates L1 → L2.

`muse-glimmer-30b` was rejected for returning prose where a tool call was
required — an agent loop cannot use a model that will not call tools.
`gpt-oss-20b` timed out on every attempt against this endpoint.

## Caveat on latency

These numbers measure a *hosted* endpoint under someone else's scheduling, so
they say little about on-premise cost. Tier choice is justified by active
parameters, not by this table; the table only rules out models that are
unusable. Sovereign-mode equivalents (`qwen3:4b`, `qwen3:8b`) must be
re-benchmarked on the target GPU.

## Entitlement

Of 81 models listed by `/v1/models`, only 11 accept completions on this key.
`app/verify_models.py` checks the registry against the catalogue; the sweep that
found the usable subset is not committed because it burns quota.
