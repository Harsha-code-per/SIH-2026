"""Conversations: persistent, and private to their owner.

The previous store kept conversations in memory with no owner, and its list
endpoint -- which needed no sign-in -- returned every user's history. A history
sidebar built on that would have shown an engineer the administrator's
conversations. These tests pin the replacement.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.sessions import (CONTEXT_TURNS, MAX_TURNS, TITLE_CHARS, Conversations,
                          Turn, make_title)


def fresh() -> Conversations:
    return Conversations(root=Path(tempfile.mkdtemp()))


def test_a_conversation_is_private_to_its_owner():
    s = fresh()
    c = s.create("admin")
    s.add_turn("admin", c.id, Turn(prompt="confidential", answer="yes"))
    assert s.get("arun", c.id) is None, "another user must not read it"
    assert s.rename("arun", c.id, "hijacked") is None, "or rename it"
    assert s.delete("arun", c.id) is False, "or delete it"
    assert s.list("arun") == [], "or see it listed"
    assert s.get("admin", c.id).title == "confidential"


def test_someone_elses_id_starts_a_new_conversation_rather_than_joining_it():
    """Resolving to a fresh conversation, not an error, means the endpoint
    never confirms that another user's id exists."""
    s = fresh()
    theirs = s.create("admin")
    s.add_turn("admin", theirs.id, Turn(prompt="secret", answer="x"))
    mine = s.get_or_create("arun", theirs.id)
    assert mine.id != theirs.id and mine.owner == "arun" and not mine.turns


def test_conversations_survive_a_restart():
    root = Path(tempfile.mkdtemp())
    a = Conversations(root=root)
    c = a.create("arun")
    a.add_turn("arun", c.id, Turn(prompt="Pump P-204 vibration", answer="Zone D",
                                  verdict="ok", decision={"tier": "L2"}))
    b = Conversations(root=root)
    got = b.get("arun", c.id)
    assert got and got.turns[0].answer == "Zone D"
    assert got.turns[0].verdict == "ok" and got.turns[0].decision["tier"] == "L2"


def test_an_empty_conversation_is_not_listed_or_saved():
    """Clicking New chat and walking away should not litter the sidebar."""
    s = fresh()
    s.create("arun")
    assert s.list("arun") == []
    assert not (s.root / "arun.json").exists()


def test_the_list_is_newest_first():
    import time
    s = fresh()
    a, b = s.create("arun"), s.create("arun")
    s.add_turn("arun", a.id, Turn(prompt="first", answer="1"))
    time.sleep(0.01)
    s.add_turn("arun", b.id, Turn(prompt="second", answer="2"))
    assert [c["title"] for c in s.list("arun")] == ["second", "first"]


def test_the_title_is_the_first_prompt_cut_at_a_word():
    assert make_title("Short one") == "Short one"
    long = "Pump P-204 drive-end vibration is 8.2 mm/s RMS, up from 6.5 last month"
    t = make_title(long)
    assert t.endswith("…") and len(t) <= TITLE_CHARS + 1
    assert not t[:-1].endswith(" ") and long.startswith(t[:-1])
    assert make_title("   ") == "New conversation"


def test_the_title_comes_from_the_first_turn_only():
    s = fresh()
    c = s.create("arun")
    s.add_turn("arun", c.id, Turn(prompt="What zone is 8.2 mm/s?", answer="D"))
    s.add_turn("arun", c.id, Turn(prompt="And who approves it?", answer="Head"))
    assert s.get("arun", c.id).title == "What zone is 8.2 mm/s?"


def test_rename_trims_and_refuses_empty():
    s = fresh()
    c = s.create("arun")
    s.add_turn("arun", c.id, Turn(prompt="x", answer="y"))
    assert s.rename("arun", c.id, "  Pump   review  ").title == "Pump review"
    assert s.rename("arun", c.id, "   ") is None


def test_replayed_context_is_bounded_but_history_is_kept():
    """Every turn stays visible; only recent ones are sent to the model."""
    s = fresh()
    c = s.create("arun")
    for i in range(CONTEXT_TURNS + 5):
        s.add_turn("arun", c.id, Turn(prompt=f"q{i}", answer=f"a{i}"))
    got = s.get("arun", c.id)
    assert len(got.turns) == CONTEXT_TURNS + 5
    assert len(got.history()) == CONTEXT_TURNS * 2
    assert got.history()[-1]["content"] == f"a{CONTEXT_TURNS + 4}"


def test_stored_turns_are_capped():
    s = fresh()
    c = s.create("arun")
    for i in range(MAX_TURNS + 3):
        c.add(Turn(prompt=f"q{i}", answer="a"))
    assert len(c.turns) == MAX_TURNS and c.turns[-1].prompt == f"q{MAX_TURNS + 2}"


def test_an_attachment_carries_to_later_turns():
    s = fresh()
    c = s.create("arun")
    s.add_turn("arun", c.id, Turn(prompt="read", answer="ok", attachment="data/uploads/r.pdf"))
    s.add_turn("arun", c.id, Turn(prompt="and the temperature?", answer="79"))
    assert s.get("arun", c.id).carried_attachment() == "data/uploads/r.pdf"


def test_an_owner_name_cannot_become_a_path_traversal():
    s = fresh()
    for bad in ("../etc", "a/b", "", "x" * 65, "Admin"):
        try:
            s.list(bad)
            assert False, f"accepted {bad!r}"
        except ValueError:
            pass


def test_the_store_file_is_private():
    s = fresh()
    c = s.create("arun")
    s.add_turn("arun", c.id, Turn(prompt="x", answer="y"))
    assert oct((s.root / "arun.json").stat().st_mode & 0o777) == "0o600"


def test_reasoning_survives_a_restart_and_old_files_still_load():
    """Reasoning is shown inline under past answers, so it is stored with the
    turn; files written before the field existed must still load."""
    import json
    root = Path(tempfile.mkdtemp())
    a = Conversations(root=root)
    c = a.create("admin")
    a.add_turn("admin", c.id, Turn(prompt="p", answer="a", thinking="because"))
    assert Conversations(root=root).get("admin", c.id).turns[0].thinking == "because"

    f = next(root.glob("*.json"))
    data = json.loads(f.read_text())
    for conv in (data.values() if isinstance(data, dict) else data):
        for t in (conv["turns"] if isinstance(conv, dict) else []):
            t.pop("thinking", None)
    f.write_text(json.dumps(data))
    assert Conversations(root=root).get("admin", c.id).turns[0].thinking == ""
