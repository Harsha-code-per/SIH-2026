"""Follow-up turns.

A workbench that forgets between questions is not the tool the problem
statement describes: an engineer asks about a reading, then what the SOP
requires, then for it as a note -- three turns about one thing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.sessions import MAX_TURNS, Sessions, Turn


def test_a_new_session_gets_an_id_and_is_remembered():
    s = Sessions()
    a = s.get(None)
    assert a.id and s.get(a.id) is a


def test_history_alternates_user_and_assistant():
    s = Sessions().get(None)
    s.add(Turn(prompt="what is the reading?", answer="8.2 mm/s"))
    s.add(Turn(prompt="and the limit?", answer="7.1 mm/s"))
    h = s.history()
    assert [m["role"] for m in h] == ["user", "assistant", "user", "assistant"]
    assert h[0]["content"] == "what is the reading?"
    assert h[-1]["content"] == "7.1 mm/s"


def test_a_turn_with_no_answer_contributes_only_the_question():
    s = Sessions().get(None)
    s.add(Turn(prompt="failed task", answer=""))
    assert [m["role"] for m in s.history()] == ["user"]


def test_history_is_bounded():
    """An unbounded conversation eventually exceeds the context window."""
    s = Sessions().get(None)
    for i in range(MAX_TURNS + 6):
        s.add(Turn(prompt=f"q{i}", answer=f"a{i}"))
    assert len(s.turns) == MAX_TURNS
    assert s.turns[-1].prompt == f"q{MAX_TURNS + 5}", "newest must be kept"
    assert s.turns[0].prompt == "q6", "oldest must be dropped"


def test_an_attachment_carries_to_later_turns():
    """"And the temperature?" must still know which report is being discussed."""
    s = Sessions().get(None)
    s.add(Turn(prompt="read this", answer="ok", attachment="data/uploads/r.pdf"))
    s.add(Turn(prompt="and the temperature?", answer="79 C"))
    assert s.carried_attachment() == "data/uploads/r.pdf"


def test_no_attachment_carries_nothing():
    s = Sessions().get(None)
    s.add(Turn(prompt="hello", answer="hi"))
    assert s.carried_attachment() is None


def test_idle_sessions_are_evicted():
    import time
    from app import sessions as S
    s = Sessions()
    old = s.get(None)
    old.touched = time.time() - S.IDLE_SECONDS - 10
    s.get(None)                      # triggers eviction
    assert old.id not in s._s


def test_session_count_is_capped():
    from app import sessions as S
    s = Sessions()
    for _ in range(S.MAX_SESSIONS + 5):
        s.get(None)
    assert len(s._s) <= S.MAX_SESSIONS


def test_dropping_a_session_reports_whether_it_existed():
    s = Sessions()
    a = s.get(None)
    assert s.drop(a.id) is True
    assert s.drop(a.id) is False
