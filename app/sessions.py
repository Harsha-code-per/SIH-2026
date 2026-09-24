"""Conversations: persistent, and owned.

A workbench that forgets between questions is not the tool the problem
statement describes, and one that forgets between restarts cannot show a
history sidebar. Conversations are kept on disk, one JSON file per user in
data/conversations/.

Ownership is enforced here, in the store, rather than in each endpoint. Every
read and write takes the owner, and a conversation that belongs to someone else
is indistinguishable from one that does not exist. An endpoint cannot forget to
check what it is never given the chance to skip. The previous in-memory store
had no owner at all, and its list endpoint returned every user's history.

A JSON file per user rather than a database: a handful of accounts and a few
hundred conversations each do not justify a second thing to deploy, back up and
air-gap. ponytail: whole-file rewrite per turn; move to SQLite if a user's file
passes a few megabytes.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "conversations"

CONTEXT_TURNS = 12      # replayed to the model; older turns stay visible, not sent
MAX_TURNS = 200         # kept per conversation, so one file cannot grow without bound
TITLE_CHARS = 60


@dataclass
class Turn:
    prompt: str
    answer: str
    evidence: list[dict] = field(default_factory=list)
    deliverables: list[dict] = field(default_factory=list)
    attachment: str | None = None
    decision: dict = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    verdict: str | None = None
    ts: float = field(default_factory=time.time)


@dataclass
class Conversation:
    id: str
    owner: str
    title: str = "New conversation"
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    turns: list[Turn] = field(default_factory=list)

    def add(self, turn: Turn) -> None:
        if not self.turns:
            self.title = make_title(turn.prompt)
        self.turns.append(turn)
        del self.turns[:-MAX_TURNS]
        self.updated = time.time()

    def history(self) -> list[dict]:
        """Recent turns as chat messages.

        Only question and answer. Replaying tool calls would refill the context
        with passages the model has already used, and the citations in the
        answer say where they came from. Bounded, so a long conversation does
        not outgrow the context window.
        """
        out: list[dict] = []
        for t in self.turns[-CONTEXT_TURNS:]:
            out.append({"role": "user", "content": t.prompt})
            if t.answer:
                out.append({"role": "assistant", "content": t.answer})
        return out

    def carried_attachment(self) -> str | None:
        """The latest attachment, so "and the temperature?" still knows which
        report is being discussed."""
        for t in reversed(self.turns):
            if t.attachment:
                return t.attachment
        return None

    def summary(self) -> dict:
        return {"id": self.id, "title": self.title, "created": self.created,
                "updated": self.updated, "turns": len(self.turns)}

    def full(self) -> dict:
        return self.summary() | {"turns": [asdict(t) for t in self.turns]}


def make_title(prompt: str) -> str:
    """The first prompt, cut at a word boundary."""
    text = " ".join(prompt.split())
    if len(text) <= TITLE_CHARS:
        return text or "New conversation"
    cut = text[:TITLE_CHARS].rsplit(" ", 1)[0]
    return (cut or text[:TITLE_CHARS]) + "…"


_SAFE = re.compile(r"^[a-z0-9_.-]{1,64}$")


class Conversations:
    def __init__(self, root: Path = STORE):
        self.root = root
        self._cache: dict[str, dict[str, Conversation]] = {}
        self._lock = threading.Lock()

    # -- storage ------------------------------------------------------------
    def _path(self, owner: str) -> Path:
        # The owner becomes a filename. Usernames are validated at creation,
        # but this is the line that would turn a crafted one into a path
        # traversal, so it checks again rather than trusting.
        if not _SAFE.match(owner):
            raise ValueError(f"unusable owner name {owner!r}")
        return self.root / f"{owner}.json"

    def _load(self, owner: str) -> dict[str, Conversation]:
        if owner not in self._cache:
            path = self._path(owner)
            convs: dict[str, Conversation] = {}
            if path.exists():
                for raw in json.loads(path.read_text()):
                    turns = [Turn(**t) for t in raw.pop("turns", [])]
                    c = Conversation(**raw, turns=turns)
                    convs[c.id] = c
            self._cache[owner] = convs
        return self._cache[owner]

    def _save(self, owner: str) -> None:
        path = self._path(owner)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(c) for c in self._load(owner).values()]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, default=str))
        os.chmod(tmp, 0o600)
        tmp.replace(path)            # atomic: a crash cannot truncate history

    # -- the interface ------------------------------------------------------
    def create(self, owner: str) -> Conversation:
        with self._lock:
            c = Conversation(id=uuid.uuid4().hex[:16], owner=owner)
            self._load(owner)[c.id] = c
            return c                 # saved on its first turn, not before

    def get(self, owner: str, cid: str | None) -> Conversation | None:
        """Someone else's conversation reads as absent, never as forbidden --
        a distinct answer would confirm the id exists."""
        if not cid:
            return None
        return self._load(owner).get(cid)

    def get_or_create(self, owner: str, cid: str | None) -> Conversation:
        return self.get(owner, cid) or self.create(owner)

    def list(self, owner: str) -> list[dict]:
        convs = [c for c in self._load(owner).values() if c.turns]
        return [c.summary() for c in sorted(convs, key=lambda c: -c.updated)]

    def add_turn(self, owner: str, cid: str, turn: Turn) -> Conversation:
        with self._lock:
            c = self._load(owner)[cid]
            c.add(turn)
            self._save(owner)
            return c

    def rename(self, owner: str, cid: str, title: str) -> Conversation | None:
        title = " ".join(title.split())[:120]
        with self._lock:
            c = self.get(owner, cid)
            if not c or not title:
                return None
            c.title = title
            self._save(owner)
            return c

    def delete(self, owner: str, cid: str) -> bool:
        with self._lock:
            convs = self._load(owner)
            if cid not in convs:
                return False
            del convs[cid]
            self._save(owner)
            return True


CONVERSATIONS = Conversations()
