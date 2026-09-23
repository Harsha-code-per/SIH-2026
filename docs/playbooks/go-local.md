# Playbook: go local (roadmap F1)

Switch inference from hosted NIM to models on the workstation. The architecture
makes this configuration, not code: everything speaks the OpenAI protocol, and
Ollama, vLLM and NIM all serve it.

Target: one workstation with an **RTX 4090 (24GB) or better**.

## 1. Choose the models

Fill the `sovereign:` column of `models.yaml`. Suggested starting points —
**verify each is current and available when you do this**; the space moves
monthly:

| Tier | Role | Suggested | ~VRAM |
|---|---|---|---|
| L1 | cheap text, tools | Qwen3-8B / Gemma-4 E4B | 5–6 GB |
| L2 | reasoning, code, tools | Qwen3-32B Q4 or gpt-oss-20b | 16–20 GB |
| LV | scanned page transcription | GLM-OCR 0.9B / PaddleOCR-VL | 2–3 GB |
| LV2 | drawings and photos | Qwen2.5-VL-7B | 6–8 GB |

The embedding model is already local and baked into the image.

L1 and L2 must call tools reliably — test that before committing to a model
(`add-a-model.md` step 2).

## 2. Pull them

```bash
make sovereign                       # starts ollama in-network, no gateway
docker compose exec ollama ollama pull <model>
```

Models persist in `data/models/`.

Pulling needs the internet, and sovereign mode has none. Pull first with the
gateway running, or pull on another machine and copy `data/models/` across.
That is how an air-gapped site would do it anyway.

## 3. Verify

```bash
MODE=sovereign make verify-models
make prove                            # still no default route; now no gateway either
make test
```

## 4. Retune — budget a day for this

A local model follows tool-calling instructions less reliably than the hosted
120B. Expect:

- **More loop-guard activity.** `REPEATS_BEFORE_WITHDRAWAL` and
  `REPEATS_BEFORE_FORCING` in `app/agent.py` may need adjusting.
- **Different token budgets.** Set `max_tokens` per model from observation.
- **Routing changes.** On local hardware L1 should be *faster* than L2 — the
  inversion measured on the hosted endpoint goes away. Some rules that moved
  work to L2 for speed can move back.
- **Retrieval.** If the embedding model changes, rerun
  `tests/test_retrieval.py` and retune `DEFAULT_ALPHA` in `app/kb.py`.

Run the whole demo sequence (`run-the-demo.md`) and record every verdict that
is not `ok`. Each one is a tuning target.

## 5. Record the evidence

Add a local-hardware section to `docs/model-benchmark.md`: latency per tier,
tool-calling reliability, drawing and transcription accuracy on the fixtures.
The finale claim is "runs entirely on-premise" — the benchmark is what makes it
true rather than asserted.
