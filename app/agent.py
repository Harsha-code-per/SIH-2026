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

MAX_STEPS = 16

# Verdicts that a second attempt can plausibly fix, with the instruction that
# addresses each. Anything not listed here is returned as it stands rather than
# retried in the hope that it improves.
REPAIRABLE = {
    "uncited": "Every factual claim in the document must carry the passage id "
               "it came from, written as [Document.md#12]. Put the ids in the "
               "body text and in the citations list of each section. Call "
               "write_docx again with the citations included.",
    "invented-citation": "One or more citations do not match any passage you "
                         "retrieved. Use only ids that appear in the search "
                         "results you were given, and write the document again.",
    "fabricated-output": "You reported program output that the sandbox did not "
                         "print. Run the code and report exactly what it printed.",
}

# A model that repeats a tool call it has already made is not making progress,
# whichever tool it is. Retrieval is the usual offender, but the same loop
# appears on arithmetic. So the guard is general rather than per-tool, and it
# escalates: warn, then withdraw the tools it is looping on, then require an
# answer in prose. Asking a model to stop looping does not reliably stop it --
# removing the option does.
REPEATS_BEFORE_WITHDRAWAL = 2     # identical calls tolerated before tools go
REPEATS_BEFORE_FORCING = 4        # ... before tool use is disabled entirely
READ_ONLY_TOOLS = {"kb_search", "read_document", "calculate", "percent_change"}

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

An approval note is a standard document. When you write one, use these sections
in this order, each as a separate entry in `sections`:

  Subject              equipment tag and the decision being sought, one line
  Observation          measured values, dates, and how they were obtained
  Applicable criteria  the governing clause quoted, with its citation
  Deviation            the observed value against the criterion, with the
                       arithmetic shown from the calculate tool
  Recommendation       the specific action and a target date
  Approval routing     who must sign, per the SOP

Put the measurements in a table where there is more than one value.

Every section that states a fact from a document must carry its passage id,
written as [Maintenance_SOP_v7.md#7], both in the body text and in that
section's citations list. A note whose criteria cannot be traced back to the
SOP is not usable by the person who has to sign it.

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
_CITE = re.compile(
    r"[\[\u3010\uff3b(]\s*([^\[\]\u3010\u3011\uff3b\uff3d()]+?#\d+)\s*[\]\u3011\uff3d)]"
    r"|(?<![\[\w])([\w.\-]+\.(?:md|pdf|txt)#\d+)")


def _first(groups) -> str:
    return next(g for g in groups if g)


def _signature(name: str, arguments: str) -> str:
    """Stable identity for a tool call, so re-ordered JSON keys still match."""
    try:
        return name + ":" + json.dumps(json.loads(arguments), sort_keys=True)
    except (json.JSONDecodeError, TypeError):
        return f"{name}:{arguments}"


# A fenced block that the answer presents as program output. Models will happily
# narrate a plausible-looking result instead of reporting what the sandbox
# actually printed, and in an engineering context a fabricated number carries
# exactly the authority of a real one.
_CLAIMED_OUTPUT = re.compile(
    r"(?:output|result|prints?|produces?|returns?)\b[^\n]{0,40}\n+```[a-z]*\n(.*?)```",
    re.I | re.S)


def unbacked_output(answer: str, stdouts: list[str]) -> list[str]:
    """Lines the answer presents as program output that no tool actually printed."""
    haystack = "\n".join(stdouts)
    missing = []
    for block in _CLAIMED_OUTPUT.findall(answer):
        for line in block.splitlines():
            line = line.strip()
            # Ignore blank lines and pure prose; numbers are what matter here.
            if line and any(ch.isdigit() for ch in line) and line not in haystack:
                missing.append(line)
    return missing


def _docx_text(path: str) -> str:
    """Read back a generated document, so verification checks what was written
    rather than what the model said it wrote."""
    try:
        from docx import Document
        from pathlib import Path as _P
        root = _P(__file__).resolve().parent.parent
        doc = Document(root / path)
        parts = [p.text for p in doc.paragraphs]
        parts += [c.text for t in doc.tables for r in t.rows for c in r.cells]
        return "\n".join(parts)
    except Exception:
        return ""


def cited_ids(text: str) -> set[str]:
    return {_first(m).strip() for m in _CITE.findall(text)}


def normalise_citations(text: str) -> str:
    """Rewrite every citation style to [id] so deliverables read consistently."""
    return _CITE.sub(lambda m: f"[{_first(m.groups()).strip()}]", text)


class Agent:
    def __init__(self, router: Router, llm: LLM,
                 on_step: Callable[[Step], None] | None = None):
        self.router = router
        self.llm = llm
        self.on_step = on_step or (lambda s: None)
        self.steps: list[Step] = []

    def _emit(self, kind: str, label: str, **detail) -> Step:
        # Detail comes from tool payloads, which are free to contain a key
        # called "kind" or "label". Those would bind to the positional
        # parameters and raise, so they are namespaced rather than trusted.
        for reserved in ("kind", "label", "n", "ts"):
            if reserved in detail:
                detail[f"detail_{reserved}"] = detail.pop(reserved)
        s = Step(len(self.steps) + 1, kind, label, detail)
        self.steps.append(s)
        self.on_step(s)
        return s

    async def run(self, prompt: str, *, has_image: bool = False,
                  attachment: str | None = None,
                  allow_escalation: bool = True) -> dict:
        note = None
        if attachment:
            from pathlib import Path as _P
            from .ocr import classify_attachment
            from .tools import ROOT
            v = classify_attachment((ROOT / attachment).resolve())
            has_image = v["has_image"]
            self._emit("route", f"attachment · {v['kind'] or 'text'}",
                       path=attachment, **{f"file_{k}": val for k, val in v.items()})
            tool = {"page": "parse_page on each page that has no text layer",
                    "drawing": "describe_image"}.get(v["kind"], "read_document")
            note = (f"The user attached a file at: {attachment}\n"
                    f"Inspect it with read_document, then use {tool}.")

        decision = self.router.route(prompt, has_image=has_image,
                                     image_kind=(v["kind"] if attachment else None))
        self._emit("route", f"{decision.tier} · {decision.rule}", **decision.as_dict())

        # L0 never reaches a model.
        if decision.tier == "L0":
            try:
                name, args = T.parse_arithmetic(prompt)
            except ValueError as e:
                self._emit("result", "not parseable as arithmetic", error=str(e))
                name, args = "calculate", {"expression": prompt}
            self._emit("tool", name, arguments=json.dumps(args))
            out = T.call(name, args)
            self._emit("result", "deterministic result", **out)
            ok = isinstance(out, dict) and "error" not in out
            self._emit("done", "ok" if ok else "failed")
            return {"answer": out.get("steps", str(out)), "decision": decision.as_dict(),
                    "steps": [s.as_dict() for s in self.steps], "evidence": [],
                    "deliverables": [], "verdict": "ok" if ok else "failed"}

        result = await self._converse(prompt, decision, note=note)

        if allow_escalation and result["verdict"] != "ok":
            up = self.router.escalate(decision)
            if up:
                self._emit("escalate", f"{decision.tier} → {up.tier}",
                           reason=result["verdict"], model=up.model_name)
                result = await self._converse(prompt, up, note=note)
                decision = up
            elif result["verdict"] in REPAIRABLE:
                # At the top tier there is nowhere to escalate, so the run is
                # repaired in place rather than handed back flawed. This is the
                # iteration the task actually needs: the work was right, the
                # sourcing was not.
                self._emit("retry", f"repairing: {result['verdict']}",
                           hint=REPAIRABLE[result["verdict"]][:80])
                repaired = await self._converse(
                    prompt, decision, repair=REPAIRABLE[result["verdict"]], note=note)
                if repaired["verdict"] == "ok" or not result["deliverables"]:
                    result = repaired

        self._emit("done", result["verdict"])
        return {"answer": result["answer"], "decision": decision.as_dict(),
                "steps": [s.as_dict() for s in self.steps],
                "evidence": result["evidence"],
                "deliverables": result["deliverables"],
                "verdict": result["verdict"]}

    async def _converse(self, prompt: str, decision: Decision,
                        repair: str | None = None, note: str | None = None) -> dict:
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt
                     + (f"\n\n{note}" if note else "")
                     + (f"\n\nIMPORTANT: {repair}" if repair else "")}]
        evidence: dict[str, dict] = {}
        deliverables: list[dict] = []
        stdouts: list[str] = []           # what the sandbox really printed
        sandbox_runs = 0
        sandbox_ok = 0
        searched = False                  # did the task ask the knowledge base?
        retrieval_broken: str | None = None
        seen: dict[str, dict] = {}        # call signature -> cached result
        repeats = 0
        narrowed = False
        budget = decision.max_tokens

        for _ in range(MAX_STEPS):
            # Withdraw the tools it is looping on, then tool use entirely.
            if repeats >= REPEATS_BEFORE_FORCING:
                offered, force_text = [], True
            elif repeats >= REPEATS_BEFORE_WITHDRAWAL:
                offered = [n for n in T.TOOLS if n not in READ_ONLY_TOOLS]
                force_text = False
            else:
                offered, force_text = list(T.TOOLS), False

            if repeats >= REPEATS_BEFORE_WITHDRAWAL and not narrowed:
                narrowed = True
                self._emit("verify", "repeating itself; tools withdrawn",
                           repeats=repeats, passages=len(evidence))
                messages.append({"role": "user", "content":
                    "You are repeating calls you have already made. Those tools "
                    "are no longer available. Produce the requested output now "
                    "from what you already have:\n" + "\n".join(
                        f"[{pid}] {p['cite']}: {p['text'][:300]}"
                        for pid, p in evidence.items())})

            up = self.router.escalate(decision)
            r = await self.llm.chat(
                decision.model_name, messages,
                tools=None if force_text else T.schemas(offered),
                max_tokens=budget, fallback=up.model_name if up else None)
            if self.llm.last_fallback:
                was, now = self.llm.last_fallback
                self._emit("escalate", f"{was} unavailable → {now}",
                           reason="endpoint saturated")
                self.llm.last_fallback = None

            choice = r.choices[0]
            msg = choice.message
            calls = getattr(msg, "tool_calls", None)

            # A reasoning model can spend its whole budget thinking and emit
            # nothing at all. That is an exhausted turn, not an empty answer --
            # give it more room rather than reporting failure.
            if (choice.finish_reason == "length" and not calls
                    and not (msg.content or "").strip()):
                if budget < 16384:
                    budget = min(budget * 2, 16384)
                    self._emit("retry", f"token budget exhausted → {budget}",
                               finish_reason="length")
                    continue
                return {"answer": "", "evidence": list(evidence.values()),
                        "deliverables": deliverables, "verdict": "truncated"}

            if not calls:
                answer = normalise_citations((msg.content or "").strip())
                return {"answer": answer, "evidence": list(evidence.values()),
                        "deliverables": deliverables,
                        "verdict": self._verify(answer, evidence, deliverables, stdouts,
                                                searched, retrieval_broken,
                                                sandbox_runs, sandbox_ok)}

            messages.append({
                "role": "assistant", "content": msg.content or "",
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name,
                                             "arguments": c.function.arguments}}
                               for c in calls]})

            for c in calls:
                name = c.function.name
                self._emit("tool", name, arguments=c.function.arguments)
                sig = _signature(name, c.function.arguments)

                if sig in seen:
                    repeats += 1
                    self._emit("result", "repeat of an earlier call",
                               repeats=repeats, tool=name)
                    messages.append({"role": "tool", "tool_call_id": c.id,
                        "content": json.dumps({
                            "repeat": True,
                            "note": "You already made this exact call. Use the "
                                    "result you were given and move on.",
                            "previous_result": seen[sig]}, default=str)[:4000]})
                    continue

                out = await asyncio.to_thread(T.call, name, c.function.arguments)
                seen[sig] = out

                if name == "kb_search":
                    searched = True
                    if out.get("error"):
                        retrieval_broken = out["error"]
                        self._emit("error", "retrieval failed", error=out["error"])
                    for psg in out.get("passages", []):
                        evidence[psg["id"]] = psg
                    if not out.get("error"):
                        self._emit("result", f"{out.get('count', 0)} passages",
                                   cites=[psg["cite"] for psg in out.get("passages", [])])
                elif name == "run_python":
                    sandbox_runs += 1
                    sandbox_ok += bool(out.get("ok"))
                    stdouts.append(str(out.get("stdout", "")))
                    self._emit("result", "sandbox exit "
                               f"{out.get('exit_code')} · {out.get('isolation', '')}",
                               stdout=str(out.get("stdout", ""))[:1200],
                               stderr=str(out.get("stderr", ""))[:400])
                elif name in ("write_docx", "write_xlsx") and "path" in out:
                    deliverables.append(out)
                    self._emit("result", out["path"], **out)
                else:
                    self._emit("result", name,
                               **({"error": out["error"]} if isinstance(out, dict)
                                  and "error" in out else {"output": str(out)[:400]}))

                messages.append({"role": "tool", "tool_call_id": c.id,
                                 "content": json.dumps(out, default=str)[:6000]})

        return {"answer": normalise_citations((msg.content or "").strip()),
                "evidence": list(evidence.values()), "deliverables": deliverables,
                "verdict": "ok" if deliverables else "step-limit"}

    def _verify(self, answer: str, evidence: dict, deliverables: list,
                stdouts: list[str] | None = None, searched: bool = False,
                retrieval_broken: str | None = None,
                sandbox_runs: int = 0, sandbox_ok: int = 0) -> str:
        """Cheap post-checks. Each failure is a reason to escalate, not to hide."""
        if not answer and not deliverables:
            return "empty"

        # A model may write buggy code, see the error, and fix it -- that is the
        # loop working. But if it ran code and nothing ever succeeded, the task
        # was not verified in a sandbox, whatever the prose says about it.
        if sandbox_runs and not sandbox_ok:
            self._emit("verify", "no sandbox run succeeded",
                       attempted=sandbox_runs, succeeded=0)
            return "sandbox-failed"

        # A task that reached for the knowledge base and got nothing back is
        # ungrounded, whatever it went on to produce. Passing it because there
        # were no citations to contradict would invert the whole check.
        if searched and not evidence:
            self._emit("verify", "retrieval returned nothing; output is ungrounded",
                       reason=retrieval_broken or "no passages matched")
            return "ungrounded"

        if stdouts:
            fake = unbacked_output(answer, stdouts)
            if fake:
                self._emit("verify", "reported output the sandbox never printed",
                           lines=fake[:5])
                return "fabricated-output"

        # When a document was produced, the citations that matter are the ones
        # inside it. The chat reply is a receipt ("note created"), and demanding
        # sources there would fail a perfectly well-sourced deliverable.
        checked = answer
        if deliverables:
            checked = "\n".join(_docx_text(d["path"]) for d in deliverables) or answer

        known = set(evidence)
        if evidence:
            cited = cited_ids(checked)
            if not cited:
                self._emit("verify",
                           "deliverable cites nothing" if deliverables
                           else "no citations in answer",
                           retrieved=len(known))
                return "uncited"
            invented = cited - known
            if invented:
                # The failure that matters most: a source that does not exist is
                # worse than no source at all.
                self._emit("verify", "citations do not resolve",
                           invented=sorted(invented))
                return "invented-citation"
        self._emit("verify", "checks passed",
                   citations=len(cited_ids(checked)), deliverables=len(deliverables))
        return "ok"
