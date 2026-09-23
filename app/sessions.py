"""Conversation state.

A workbench that forgets everything between questions is not the tool the
problem statement describes. An engineer asks about a reading, then asks what
the SOP requires, then asks for it as a note -- three turns about one thing.

Kept in memory and bounded: this is per-workstation software, and a
conversation that outlives the process is not worth a database. The audit log
on disk is the durable record.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

MAX_TURNS = 12          # per conversation, oldest dropped first
MAX_SESSIONS = 50       # least recently used dropped first
IDLE_SECONDS = 4 * 3600


@dataclass
class Turn:
    prompt: str
    answer: str
    evidence: list[dict] = field(default_factory=list)
    deliverables: list[dict] = field(default_factory=list)
    attachment: str | None = None
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    id: str
    turns: list[Turn] = field(default_factory=list)
    touched: float = field(default_factory=time.time)

    def add(self, turn: Turn) -> None:
        self.turns.append(turn)
        del self.turns[:-MAX_TURNS]
        self.touched = time.time()

    def history(self) -> list[dict]:
        """Prior turns as chat messages.

        Only the question and the answer. Replaying tool calls would refill the
        context with retrieved passages the model has already used, and the
        citations in the answer already say where they came from.
        """
        out: list[dict] = []
        for t in self.turns:
            out.append({"role": "user", "content": t.prompt})
            if t.answer:
                out.append({"role": "assistant", "content": t.answer})
        return out

    def carried_attachment(self) -> str | None:
        """The most recent attachment, so "and the temperature?" still knows
        which report is being discussed."""
        for t in reversed(self.turns):
            if t.attachment:
                return t.attachment
        return None

    def as_dict(self) -> dict:
        return {"id": self.id, "turns": len(self.turns), "touched": self.touched,
                "preview": self.turns[0].prompt[:80] if self.turns else ""}


class Sessions:
    def __init__(self) -> None:
        self._s: dict[str, Session] = {}

    def get(self, sid: str | None) -> Session:
        if sid and sid in self._s:
            s = self._s[sid]
            s.touched = time.time()
            self._evict()
            return s
        s = Session(id=sid or uuid.uuid4().hex[:12])
        self._s[s.id] = s
        # Evicted after inserting, or the cap is exceeded by the new arrival.
        self._evict()
        return s

    def _evict(self) -> None:
        now = time.time()
        for sid, s in list(self._s.items()):
            if now - s.touched > IDLE_SECONDS:
                del self._s[sid]
        while len(self._s) > MAX_SESSIONS:
            oldest = min(self._s, key=lambda k: self._s[k].touched)
            del self._s[oldest]

    def all(self) -> list[dict]:
        return [s.as_dict() for s in
                sorted(self._s.values(), key=lambda s: -s.touched)]

    def drop(self, sid: str) -> bool:
        return self._s.pop(sid, None) is not None


SESSIONS = Sessions()
