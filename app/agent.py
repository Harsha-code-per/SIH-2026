"""The agent loop.

A plain tool-calling loop. Eighty lines that can be read at 3am beats a
framework whose control flow lives in someone else's repository.

Two things make it more than a chat wrapper:

  grounding    the model is required to cite retrieved passages, and a check
               after the fact rejects claims that cite nothing. An inspection
               finding without a traceable source is not usable by an engineer.

  escalation   if the cheap tier produces something that fails verification,
               the same task is retried one tier up rather than returned
               broken. That is the "iterate instead of answering once" the
               problem statement asks for.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import AsyncIterator, Callable

from . import tools as T
from .llm import LLM
from .router import Router, Decision

MAX_STEPS = 12

SYSTEM = """You are an engineering assistant inside a refinery's own network.

Rules you must follow:
- Search the knowledge base before stating any limit, threshold, criterion or
  approval requirement. Never rely on memory for a number that belongs to a
  document.
- Cite the passage id for every factual claim, like [Maintenance_SOP_v7.md#12].
- Compute every number with the calculate or percent_change tool. Do not do
  arithmetic yourself.
- When asked for a document deliverable, call the write tool. Do not paste the
  document into chat and call it done.
- If the knowledge base does not support a claim, say so plainly rather than
  filling the gap.

Be terse. An engineer is reading this, not a customer."""


@dataclass
class Step:
    n: int
    kind: str                     # think | tool | result | verify | escalate | done
    label: str
    detail: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return asdict(self)


# Models bracket citations in whatever style their training favoured -- ASCII
# [x], CJK full-width, or parentheses. Matching only one style silently reports
# a well-cited answer as uncited and escalates it for no reason.
_CITE = re.compile(r"[\[\u3010\uff3b(]\s*([^\[\]\u3010\u3011\uff3b\uff3d()]+?#\d+)\s*[\]\u3011\uff3d)]")


def cited_ids(text: str) -> set[str]:
    return {m.strip() for m in _CITE.findall(text)}


def normalise_citations(text: str) -> str:
    """Rewrite every citation style to [id] so deliverables read consistently."""
    return _CITE.sub(lambda m: f"[{m.group(1).strip()}]", text)


class Agent:
    def __init__(self, router: Router, llm: LLM,
                 on_step: Callable[[Step], None] | None = None):
        self.router = router
        self.llm = llm
        self.on_step = on_step or (lambda s: None)
        self.steps: list[Step] = []

    def _emit(self, kind: str, label: str, **detail) -> Step:
        s = Step(len(self.steps) + 1, kind, label, detail)
        self.steps.append(s)
        self.on_step(s)
        return s

    async def run(self, prompt: str, *, has_image: bool = False,
                  allow_escalation: bool = True) -> dict:
        decision = self.router.route(prompt, has_image=has_image)
        self._emit("route", f"{decision.tier} · {decision.rule}", **decision.as_dict())

        # L0 never reaches a model.
        if decision.tier == "L0":
            out = T.call(decision.tool or "calculate", {"expression": prompt})
            self._emit("result", "deterministic result", **out)
            return {"answer": out.get("steps", str(out)), "decision": decision.as_dict(),
                    "steps": [s.as_dict() for s in self.steps], "evidence": [],
                    "deliverables": []}

        result = await self._converse(prompt, decision)

        if allow_escalation and result["verdict"] != "ok":
            up = self.router.escalate(decision)
            if up:
                self._emit("escalate", f"{decision.tier} → {up.tier}",
                           reason=result["verdict"], model=up.model_name)
                result = await self._converse(prompt, up)
                decision = up

        self._emit("done", result["verdict"])
        return {"answer": result["answer"], "decision": decision.as_dict(),
                "steps": [s.as_dict() for s in self.steps],
                "evidence": result["evidence"],
                "deliverables": result["deliverables"],
                "verdict": result["verdict"]}

    async def _converse(self, prompt: str, decision: Decision) -> dict:
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt}]
        evidence: dict[str, dict] = {}
        deliverables: list[dict] = []

        for _ in range(MAX_STEPS):
            up = self.router.escalate(decision)
            r = await self.llm.chat(decision.model_name, messages,
                                    tools=T.schemas(), max_tokens=1536,
                                    fallback=up.model_name if up else None)
            if self.llm.last_fallback:
                was, now = self.llm.last_fallback
                self._emit("escalate", f"{was} unavailable → {now}",
                           reason="endpoint saturated")
                self.llm.last_fallback = None
            msg = r.choices[0].message
            calls = getattr(msg, "tool_calls", None)

            if not calls:
                answer = normalise_citations((msg.content or "").strip())
                return {"answer": answer, "evidence": list(evidence.values()),
                        "deliverables": deliverables,
                        "verdict": self._verify(answer, evidence, deliverables)}

            messages.append({
                "role": "assistant", "content": msg.content or "",
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name,
                                             "arguments": c.function.arguments}}
                               for c in calls]})

            for c in calls:
                self._emit("tool", c.function.name, arguments=c.function.arguments)
                out = await asyncio.to_thread(T.call, c.function.name, c.function.arguments)

                if c.function.name == "kb_search":
                    for p in out.get("passages", []):
                        evidence[p["id"]] = p
                    self._emit("result", f"{out.get('count', 0)} passages",
                               cites=[p["cite"] for p in out.get("passages", [])])
                elif c.function.name in ("write_docx", "write_xlsx") and "path" in out:
                    deliverables.append(out)
                    self._emit("result", out["path"], **out)
                else:
                    self._emit("result", c.function.name,
                               **({"error": out["error"]} if isinstance(out, dict)
                                  and "error" in out else
                                  {"output": str(out)[:400]}))

                messages.append({"role": "tool", "tool_call_id": c.id,
                                 "content": json.dumps(out, default=str)[:6000]})

        return {"answer": "Step limit reached before the task completed.",
                "evidence": list(evidence.values()), "deliverables": deliverables,
                "verdict": "step-limit"}

    def _verify(self, answer: str, evidence: dict, deliverables: list) -> str:
        """Cheap post-checks. Each failure is a reason to escalate, not to hide."""
        if not answer and not deliverables:
            return "empty"
        if evidence:
            cited = cited_ids(answer)
            known = set(evidence)
            if not cited:
                self._emit("verify", "no citations in answer", retrieved=len(known))
                return "uncited"
            invented = cited - known
            if invented:
                # The one failure mode that matters most: a source that does not
                # exist is worse than no source at all.
                self._emit("verify", "citations do not resolve",
                           invented=sorted(invented))
                return "invented-citation"
        self._emit("verify", "checks passed",
                   citations=len(cited_ids(answer)), deliverables=len(deliverables))
        return "ok"
