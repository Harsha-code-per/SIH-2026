"""Model access.

One OpenAI-compatible client, pointed wherever the current mode says. NIM,
Ollama, vLLM and llama.cpp all speak this protocol, which is what makes the
sovereign migration a config change instead of a rewrite.
"""
from __future__ import annotations

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

    async def chat(self, model: str, messages: list[dict], *,
                   tools: list[dict] | None = None,
                   temperature: float = 0.2,
                   max_tokens: int = 1536) -> Any:
        kw: dict[str, Any] = dict(model=model, messages=messages,
                                  temperature=temperature, max_tokens=max_tokens)
        if tools:
            kw |= {"tools": tools, "tool_choice": "auto"}
        return await self.client.chat.completions.create(**kw)

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
