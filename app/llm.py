"""Model access.

One OpenAI-compatible client, pointed wherever the current mode says. NIM,
Ollama, vLLM and llama.cpp all speak this protocol, which is what makes the
sovereign migration a config change instead of a rewrite.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any, Callable

from openai import AsyncOpenAI

from .router import Router


def load_dotenv(path: Path | str = ".env") -> None:
    """Minimal .env reader. Not worth a dependency."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


async def collect(stream, on_delta: Callable[[str, str], None]) -> Any:
    """Drain a streamed completion into the shape `create()` returns without
    streaming: choices[0].message.content / .tool_calls, and finish_reason.

    Tool calls arrive as fragments keyed by index -- the id and name in one
    chunk, the arguments spread over many -- and are only usable once joined.
    """
    content: list[str] = []
    calls: dict[int, dict] = {}
    finish = None
    async for chunk in stream:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        d = choice.delta
        # Reasoning models on NIM stream their thinking in a field the SDK does
        # not declare; Ollama and vLLM use `reasoning`.
        extra = getattr(d, "model_extra", None) or {}
        thinking = extra.get("reasoning_content") or extra.get("reasoning")
        if thinking:
            on_delta("thinking", thinking)
        if d.content:
            content.append(d.content)
            on_delta("token", d.content)
        for tc in d.tool_calls or []:
            slot = calls.setdefault(tc.index, {"id": None, "name": "", "arguments": ""})
            slot["id"] = tc.id or slot["id"]
            if tc.function:
                slot["name"] += tc.function.name or ""
                slot["arguments"] += tc.function.arguments or ""
        finish = choice.finish_reason or finish
    tool_calls = [NS(id=c["id"] or f"call_{i}", type="function",
                     function=NS(name=c["name"], arguments=c["arguments"] or "{}"))
                  for i, c in sorted(calls.items())]
    return NS(choices=[NS(finish_reason=finish, message=NS(
        content="".join(content), tool_calls=tool_calls or None))])


class LLM:
    def __init__(self, router: Router):
        self.router = router
        cfg = router.mode_cfg
        key_env = cfg.get("api_key_env")
        key = os.environ.get(key_env, "") if key_env else "not-needed"
        self.endpoint = os.environ.get("MODEL_ENDPOINT", cfg["endpoint"])
        # An empty key against a hosted endpoint fails deep inside a request with
        # an opaque 401. Catch it at construction, where the message can be useful.
        if key_env and not key:
            raise RuntimeError(
                f"{key_env} is unset but mode '{router.mode}' needs it. "
                f"Copy .env.example to .env, or run with MODE=sovereign."
            )
        self.client = AsyncOpenAI(base_url=self.endpoint, api_key=key, timeout=120.0)
        self.last_fallback: tuple[str, str] | None = None

    async def chat(self, model: str, messages: list[dict], *,
                   tools: list[dict] | None = None,
                   temperature: float = 0.2,
                   max_tokens: int = 1536,
                   fallback: str | None = None,
                   on_delta: Callable[[str, str], None] | None = None) -> Any:
        """Call a model, surviving a saturated shared endpoint.

        Hosted inference is someone else's capacity, and a 503 halfway through
        a live demo is indistinguishable from a broken system. Retries are
        bounded and a fallback model is tried once before giving up, so a busy
        worker degrades the answer rather than ending the run. On-premise this
        matters far less, which is rather the point.

        With `on_delta`, the reply is streamed: each piece of answer text is
        passed on as ("token", text) and each piece of the model's reasoning
        as ("thinking", text), while the whole reply is still assembled and
        returned in the same shape as a non-streamed one -- so everything
        downstream, verification included, is unchanged. A retry after text
        has gone out first sends ("reset", why), so nothing is shown twice.
        """
        kw: dict[str, Any] = dict(model=model, messages=messages,
                                  temperature=temperature, max_tokens=max_tokens)
        if tools:
            kw |= {"tools": tools, "tool_choice": "auto"}
        if on_delta:
            kw["stream"] = True
        sent = False                      # has any delta reached the caller?

        def relay(kind: str, text: str) -> None:
            nonlocal sent
            sent = True
            on_delta(kind, text)  # type: ignore[misc]

        last: Exception | None = None
        for candidate in [model] + ([fallback] if fallback and fallback != model else []):
            kw["model"] = candidate
            for attempt in range(3):
                try:
                    if sent:
                        on_delta("reset", "the endpoint dropped the reply; retrying")  # type: ignore[misc]
                        sent = False
                    r = await self.client.chat.completions.create(**kw)
                    if on_delta:
                        r = await collect(r, relay)
                    if candidate != model:
                        self.last_fallback = (model, candidate)
                    return r
                except Exception as e:
                    last = e
                    # Streamed, a saturated worker reports inside the stream
                    # as "Service temporarily overloaded" with no status code
                    # in the message, so the code is checked where it exists.
                    retryable = getattr(e, "status_code", None) in (429, 500, 502, 503, 504) \
                        or any(c in f"{e}" for c in ("503", "429", "500", "502", "504",
                                                     "ResourceExhausted", "Timeout",
                                                     "overloaded"))
                    if not retryable:
                        break
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise last  # type: ignore[misc]

    async def text(self, model: str, prompt: str, *, system: str | None = None,
                   **kw) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        r = await self.chat(model, msgs, **kw)
        return (r.choices[0].message.content or "").strip()

    async def vision(self, model: str, prompt: str, image_b64: str,
                     mime: str = "image/png", **kw) -> str:
        """Same protocol; images ride as data URIs so nothing is uploaded anywhere."""
        r = await self.chat(model, [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
        ]}], **kw)
        return (r.choices[0].message.content or "").strip()
