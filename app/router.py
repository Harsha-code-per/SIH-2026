"""Deterministic task router.

Extracts features from a request, matches them against the rules in models.yaml,
returns a decision record. No LLM call in the hot path -- the routing decision is
explainable, reproducible, and testable without a GPU.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "models.yaml"

# Regexes are ordered: first hit wins. Deliberately narrow -- a miss falls
# through to "chat", which routes to L1, which is the cheap safe default.
_ARITHMETIC = re.compile(
    r"^[\s\d.,()+\-*/%^=?]+$"                       # a bare expression
    r"|\b(?:calculate|compute|how much is)\b"        # explicit verbs
    r"|\bpercent(?:age)? (?:increase|decrease|change|of)\b"
    r"|\bwhat(?:'s| is) \d",                         # "what is 18 * 47"
    re.I,
)
_CODE = re.compile(
    r"\b(code|script|python|function|debug|refactor|unit test|program|"
    r"write a (program|script)|run this)\b",
    re.I,
)
_ANALYZE = re.compile(
    r"\b(analy[sz]e|compare|assess|evaluate|review|audit|findings?|inspect\w*"
    r"|approval note|sop|procedure|criteri(?:a|on)|clause|acceptance"
    r"|what does .{0,20}\brequire|who (?:must|should) approve|is .{0,30}(?:above|below|within))\b",
    re.I,
)
_SUMMARIZE = re.compile(r"\b(summari[sz]e|tl;?dr|brief|digest|key points)\b", re.I)

# A request for a file deliverable is never a bare calculation, whatever verbs
# it happens to contain.
_DELIVERABLE = re.compile(
    r"\b(word document|\.docx|docx|excel|\.xlsx|xlsx|spreadsheet|powerpoint|"
    r"\.pptx|pptx|presentation|approval note|draft a|produce a|generate a)\b", re.I)

# An image is a "drawing" (P&ID, schematic, photo) rather than a scanned page
# when the user says so, or when the page carries almost no machine text.
_DRAWING = re.compile(r"\b(p&?id|drawing|diagram|schematic|photo|picture|sketch)\b", re.I)


@dataclass
class Features:
    task: str = "chat"
    has_image: bool = False
    image_kind: str | None = None          # "drawing" | "page" | None
    input_tokens: int = 0
    needs_tools: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decision:
    tier: str
    model_id: str | None
    model_name: str | None
    tool: str | None
    max_tokens: int
    rule: str
    why: str
    features: dict
    mode: str
    escalates_to: str | None = None
    alternatives: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def estimate_tokens(text: str) -> int:
    """~4 chars per token. Good enough to pick a tier; we are not billing anyone."""
    return len(text) // 4


def extract_features(prompt: str, *, has_image: bool = False,
                     image_kind: str | None = None) -> Features:
    f = Features(has_image=has_image, input_tokens=estimate_tokens(prompt))
    if has_image:
        f.image_kind = image_kind or ("drawing" if _DRAWING.search(prompt) else "page")

    # Order matters, and arithmetic goes near the end. Plenty of real tasks say
    # "compute" in passing -- "check it against the SOP, compute the rise and
    # draft an approval note" is multi-step work, not a calculation. L0 may only
    # claim a request that is nothing but arithmetic.
    if _CODE.search(prompt):
        f.task = "code"
        f.needs_tools = True
    elif _ANALYZE.search(prompt) or _DELIVERABLE.search(prompt):
        f.task = "analyze"
        f.needs_tools = True
    elif _ARITHMETIC.search(prompt.strip()):
        f.task = "arithmetic"
    elif _SUMMARIZE.search(prompt):
        f.task = "summarize"
    return f


class Router:
    def __init__(self, config_path: Path | str = CONFIG, mode: str | None = None):
        self.config_path = Path(config_path)
        self.mode = mode or os.environ.get("MODE", "prototype")
        self.reload()

    def reload(self) -> None:
        """Re-read models.yaml. Adding a model is a config edit + this call."""
        self.cfg = yaml.safe_load(self.config_path.read_text())
        self.models = self.cfg["models"]
        self.rules = self.routing_rules = self.cfg["routing"]
        self.escalation = self.cfg.get("escalation", {})
        self.mode_cfg = self.cfg["modes"][self.mode]

    # -- registry -----------------------------------------------------------
    def models_for_tier(self, tier: str) -> list[dict]:
        return [m for m in self.models if m["tier"] == tier]

    def orchestrator(self) -> dict | None:
        """The best model that can actually drive a tool-calling loop.

        The vision tiers exist to *read* things; they are chosen by the tools
        that need them and cannot run a conversation. Handing the loop to one
        produced a raw JSON tool call as the final answer.
        """
        capable = [m for m in self.models if "tools" in m["caps"]]
        if not capable:
            return None
        # Strength is defined by the escalation chain -- the tier nothing
        # escalates past is the strongest. Inferring it from the order routing
        # rules happen to appear in picked the cheap tier.
        def depth(tier: str) -> int:
            seen, n = {tier}, 0
            while (nxt := self.escalation.get(tier)) and nxt not in seen:
                tier, n = nxt, n + 1
                seen.add(tier)
            return n
        return min(capable, key=lambda m: depth(m["tier"]))

    def resolve(self, model: dict) -> str:
        """Registry entry -> the model name this mode actually calls."""
        return model[self.mode]

    # -- routing ------------------------------------------------------------
    @staticmethod
    def _matches(cond: dict, f: Features) -> bool:
        for key, want in cond.items():
            if key == "input_tokens_gt":
                if f.input_tokens <= want:
                    return False
            elif key == "task":
                if f.task != want:
                    return False
            elif key == "has_image":
                if f.has_image != want:
                    return False
            elif key == "image_kind":
                if f.image_kind != want:
                    return False
            else:
                raise ValueError(f"unknown routing condition: {key}")
        return True

    def route(self, prompt: str, *, has_image: bool = False,
              image_kind: str | None = None) -> Decision:
        f = extract_features(prompt, has_image=has_image, image_kind=image_kind)
        for rule in self.rules:
            if self._matches(rule.get("if") or {}, f):
                then = rule["then"]
                tier = then["tier"]
                candidates = self.models_for_tier(tier)
                chosen = candidates[0] if candidates else None
                return Decision(
                    tier=tier,
                    model_id=chosen["id"] if chosen else None,
                    model_name=self.resolve(chosen) if chosen else None,
                    tool=then.get("tool"),
                    max_tokens=(chosen or {}).get("max_tokens", 2048),
                    rule=rule["name"],
                    why=rule["why"],
                    features=f.as_dict(),
                    mode=self.mode,
                    escalates_to=self.escalation.get(tier),
                    alternatives=[m["id"] for m in candidates[1:]],
                )
        raise RuntimeError("no routing rule matched; models.yaml needs a default")

    def escalate(self, decision: Decision) -> Decision | None:
        """One tier up after a failed verification. Returns None at the ceiling."""
        nxt = self.escalation.get(decision.tier)
        if not nxt:
            return None
        candidates = self.models_for_tier(nxt)
        if not candidates:
            return None
        chosen = candidates[0]
        return Decision(
            tier=nxt,
            model_id=chosen["id"],
            model_name=self.resolve(chosen),
            tool=None,
            max_tokens=chosen.get("max_tokens", 2048),
            rule=f"escalation-from-{decision.tier}",
            why="Previous tier failed verification; retrying one tier up.",
            features=decision.features,
            mode=self.mode,
            escalates_to=self.escalation.get(nxt),
        )
