# Playbook: add a model

Put a new open-weight model behind a tier. **This must never need a code
change** — that is the problem statement's "addable later without redesigning
the system". If you find yourself editing Python to add a model, stop.

## 1. Confirm it is usable, not just listed

The NIM catalogue lists more models than a key can call (11 of 81 on ours).
Check the model accepts a completion before registering it:

```bash
set -a && . ./.env && set +a
curl -s https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $NVIDIA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"<model-id>","messages":[{"role":"user","content":"say ok"}],"max_tokens":8}'
```

`200` is usable. `404` means not entitled. `403` means the key is wrong.

## 2. If it will drive the agent loop, check it calls tools

A model that answers in prose where a tool call is required cannot run the loop
(`muse-glimmer-30b` was rejected for exactly this). Send a request with a
`tools` array and confirm the response has `tool_calls`. Vision-only models do
not need this — they are called by tools, not by the loop (D-5).

## 3. Register it in `models.yaml`

```yaml
  - id: reason-large            # unique, short
    tier: L2                    # L1 | L2 | LV | LV2
    caps: [text, tools, code]   # "tools" only if it passed step 2
    ctx: 32768
    max_tokens: 8192            # reasoning models need headroom (D-22)
    why: "What this model is for, in one line — shown in the UI."
    prototype: vendor/model-id  # the hosted name
    sovereign: local-name:tag   # the local name; required, even if a guess
```

Rules the tests enforce:
- Every model needs **both** a `prototype` and a `sovereign` value.
- The first model in a tier is the one routing chooses.

## 4. Load it

Models tab → **Reload registry**, or `make restart`. Then:

```bash
make verify-models        # every id present in the live catalogue
make test                 # router and sovereignty tests still pass
```

## 5. Measure before you trust it

Add a row to `docs/model-benchmark.md`: median latency over three runs, whether
it calls tools, and for vision models the accuracy on the fixtures. Pick from
evidence — two of our first four guesses were unusable.
