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

## Vision: transcribing a scanned page

Same scanned page (`scripts/make_scanned_sample.py`, no text layer), scored on
whether five known values survive transcription: `8.2`, `P-204`, `2960`, `79`,
`CM/CDU/2026/0847`.

| Model | key values | output | behaviour |
|---|---|---|---|
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | **5/5** | 1313 b | verbatim, table structure preserved |
| `meta/llama-3.2-11b-vision-instruct` | 4/5 | 2046 b | describes the page rather than transcribing it |
| `nvidia/nemotron-parse-2.0` | — | — | repeated tokens, then 502 |

`nemotron-parse-2.0` is a purpose-built document parser with its own request
shape; driven through plain chat-completions it degenerates. It is the right
class of model — a 0.9B document VLM beats general VLMs on OmniDocBench — but
it needs its own client, which is work for the on-premise build rather than the
prototype.

The distinction that matters for an inspection report is transcription versus
description. Llama-3.2-vision writes *about* the page ("the report details
vibration readings"); the omni model reproduces the numbers. For a document
whose whole value is its numbers, only the first is usable — so it takes the
LV tier, and Llama-3.2-vision keeps LV2 where describing a drawing is the job.

## Vision: reading an engineering drawing

Fixture is `scripts/make_pid_sample.py`, a synthetic ISA-5.1 P&ID with known
ground truth: 9 equipment and instrument tags, 3 line numbers. Drawn rather
than downloaded so "did it read the sheet" has an answer rather than an
opinion.

| Approach | time | tags | line numbers | precision |
|---|---|---|---|---|
| whole sheet, one call | 21s | 4/9 | 3/3 | clean |
| 6 tiles, sequential | 365s | **9/9** | 3/3 | **invented V-102…V-329** |
| 4 tiles, concurrent, guarded | **12s** | 7/9 | 3/3 | clean |

Three things were wrong, in order of how much they mattered.

A full sheet downscales `FIC-2043` to a few pixels tall, so most tags were
unreadable. Reading overlapping tiles at full resolution fixes that.

The tags were then missed by the *extraction pattern*, not the model: it
required two-letter prefixes, so `V-101`, `P-204A` and `E-102` could never
match. Worth remembering that a retrieval or extraction failure usually is not
the model.

ISA-5.1 draws an instrument as a circle with function letters on one line and
the loop number beneath. Read literally that is two fragments, and every
instrument on the sheet was lost until the prompt described the convention.

The sequential run reached 9/9 and simultaneously invented three hundred
vessels — a tile lost its place and began counting. Recall was perfect and
precision was worthless, which is the worse failure: an engineer can work
around a missing tag and cannot work around an invented one. Degenerate output
is now detected (repeated lines, or a run of six consecutive numbers under one
prefix), retried once with a tighter budget, and dropped with the region named
in the output if it still fails.

Remaining errors are function-letter confusions inside bubbles — `FIC-2043`
read as `FI-2043`, `LIC-1011` as `V-1011`. The numbers are right and the
prefix is wrong. The interface shows the extracted tags so an engineer checks
them, which is the correct division of labour for drawing work anyway.
