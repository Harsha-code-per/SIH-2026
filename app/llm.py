"""Model access.

One OpenAI-compatible client, pointed wherever the current mode says. NIM,
Ollama, vLLM and llama.cpp all speak this protocol, which is what makes the
sovereign migration a config change instead of a rewrite.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

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
                   fallback: str | None = None) -> Any:
        """Call a model, surviving a saturated shared endpoint.

        Hosted inference is someone else's capacity, and a 503 halfway through
        a live demo is indistinguishable from a broken system. Retries are
        bounded and a fallback model is tried once before giving up, so a busy
        worker degrades the answer rather than ending the run. On-premise this
        matters far less, which is rather the point.
        """
        kw: dict[str, Any] = dict(model=model, messages=messages,
                                  temperature=temperature, max_tokens=max_tokens)
        if tools:
            kw |= {"tools": tools, "tool_choice": "auto"}

        last: Exception | None = None
        for candidate in [model] + ([fallback] if fallback and fallback != model else []):
            kw["model"] = candidate
            for attempt in range(3):
                try:
                    r = await self.client.chat.completions.create(**kw)
                    if candidate != model:
                        self.last_fallback = (model, candidate)
                    return r
                except Exception as e:
                    last = e
                    retryable = any(c in f"{e}" for c in ("503", "429", "ResourceExhausted",
                                                          "Timeout", "502"))
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
