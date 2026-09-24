"""Streaming. The interface shows the answer as it arrives, so what streams out
must end up being exactly the answer that was verified -- nothing left over
from a turn that became a tool call, a retry, or a repair.

A fake client stands in for the endpoint; the stream shapes are the ones NIM
sends (reasoning in an undeclared `reasoning_content` field, tool calls split
into fragments by index).
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import Agent
from app.llm import LLM, collect
from app.router import Router


def chunk(content=None, thinking=None, call=None, finish=None):
    """call = (index, id, name, arguments-fragment)"""
    tool_calls = None
    if call:
        i, cid, name, args = call
        tool_calls = [NS(index=i, id=cid, function=NS(name=name, arguments=args))]
    delta = NS(content=content, tool_calls=tool_calls,
               model_extra={"reasoning_content": thinking} if thinking else {})
    return NS(choices=[NS(delta=delta, finish_reason=finish)])


async def stream(chunks, fail_after=None):
    for n, c in enumerate(chunks):
        if fail_after is not None and n == fail_after:
            raise RuntimeError("Error code: 503 - worker saturated")
        yield c


class FakeCompletions:
    def __init__(self, turns):
        self.turns = list(turns)          # each: (chunks, fail_after)

    async def create(self, **kw):
        assert kw.get("stream"), "streaming was requested but not sent"
        chunks, fail_after = self.turns.pop(0)
        return stream(chunks, fail_after)


def fake_llm(router, turns):
    llm = LLM.__new__(LLM)                # no key needed; nothing leaves
    llm.router = router
    llm.last_fallback = None
    llm.client = NS(chat=NS(completions=FakeCompletions(turns)))
    return llm


def test_collect_assembles_what_create_would_have_returned():
    seen = []
    r = asyncio.run(collect(stream([
        chunk(thinking="User wants a "), chunk(thinking="calculation."),
        chunk(content="Let me "), chunk(content="compute."),
        chunk(call=(0, "call_1", "calculate", '{"expr')),
        chunk(call=(0, None, "", 'ession": "1+1"}')),
        chunk(finish="tool_calls"),
    ]), lambda kind, text: seen.append((kind, text))))
    msg = r.choices[0].message
    assert msg.content == "Let me compute."
    assert r.choices[0].finish_reason == "tool_calls"
    [c] = msg.tool_calls
    assert (c.id, c.function.name, c.function.arguments) == \
        ("call_1", "calculate", '{"expression": "1+1"}')
    assert "".join(t for k, t in seen if k == "thinking") == "User wants a calculation."
    assert "".join(t for k, t in seen if k == "token") == "Let me compute."


def test_a_reply_without_tool_calls_has_none():
    r = asyncio.run(collect(stream([chunk(content="Four"), chunk(finish="stop")]),
                            lambda *_: None))
    assert r.choices[0].message.tool_calls is None


def test_streamed_tokens_end_as_exactly_the_final_answer():
    """Narration before a tool call streams out, then must be withdrawn; what
    remains on screen is the answer the agent returns and verifies."""
    router = Router()
    decision = router.route("Analyse the vibration trend against the SOP")
    events = []
    agent = Agent(router, fake_llm(router, [
        ([chunk(content="Let me work that out."),
          chunk(call=(0, "c1", "calculate", '{"expression": "(8.2-6.5)/6.5*100"}')),
          chunk(finish="tool_calls")], None),
        ([chunk(thinking="26.15 it is."),
          chunk(content="The rise is "), chunk(content="26.15%."),
          chunk(finish="stop")], None),
    ]), on_delta=lambda kind, text: events.append((kind, text)))
    result = asyncio.run(agent._converse("How much did it rise?", decision))

    kinds = [k for k, _ in events]
    assert "reset" in kinds, "narration before a tool call was never withdrawn"
    last_reset = len(kinds) - 1 - kinds[::-1].index("reset")
    shown = "".join(t for k, t in events[last_reset + 1:] if k == "token")
    assert shown == result["answer"] == "The rise is 26.15%."
    assert ("thinking", "26.15 it is.") in events


def test_a_retry_after_partial_output_withdraws_it_first():
    """A stream that dies halfway and is retried must not show its first half
    followed by the whole second attempt."""
    router = Router()
    events = []
    llm = fake_llm(router, [
        ([chunk(content="Half an ans"), chunk(content="wer")], 1),
        ([chunk(content="A whole answer."), chunk(finish="stop")], None),
    ])
    r = asyncio.run(llm.chat("m", [], on_delta=lambda k, t: events.append((k, t))))
    assert r.choices[0].message.content == "A whole answer."
    assert [k for k, _ in events] == ["token", "reset", "token"]


def test_an_overload_reported_inside_the_stream_is_retried():
    """NIM reports a saturated worker mid-stream as a bare "Service temporarily
    overloaded" -- no status code in the text. It must be retried like a 503,
    not end the run."""
    router = Router()
    llm = fake_llm(router, [])
    calls = {"n": 0}

    async def create(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            async def dying():
                raise RuntimeError("Service temporarily overloaded")
                yield  # pragma: no cover
            return dying()
        return stream([chunk(content="fine"), chunk(finish="stop")])
    llm.client = NS(chat=NS(completions=NS(create=create)))
    r = asyncio.run(llm.chat("m", [], on_delta=lambda *_: None))
    assert r.choices[0].message.content == "fine" and calls["n"] == 2


def test_without_a_listener_nothing_streams():
    """Tools, the CLI and the tests call the client without on_delta and must
    keep getting ordinary, non-streamed completions."""
    router = Router()
    llm = fake_llm(router, [])
    sent = {}

    async def create(**kw):
        sent.update(kw)
        return NS(choices=[NS(finish_reason="stop", message=NS(content="ok", tool_calls=None))])
    llm.client = NS(chat=NS(completions=NS(create=create)))
    asyncio.run(llm.chat("m", []))
    assert "stream" not in sent


def test_a_failed_check_withdraws_the_answer_with_its_reason():
    """An answer that fails verification streamed out in full before the
    checks ran. When the agent escalates, the interface must be told to
    withdraw it and why -- not left showing the rejected text."""
    router = Router()
    events = []
    # The first reply prints a tool call instead of answering (verdict
    # "malformed"); the escalated one answers.
    agent = Agent(router, fake_llm(router, [
        ([chunk(content='{"name": "kb_search", "arguments": {}}'), chunk(finish="stop")], None),
        ([chunk(content="Summary: the pump is fine."), chunk(finish="stop")], None),
        ([chunk(content="Summary: the pump is fine."), chunk(finish="stop")], None),
    ]), on_delta=lambda kind, text: events.append((kind, text)))
    result = asyncio.run(agent.run("Summarise this note: the pump is fine."))
    resets = [t for k, t in events if k == "reset"]
    assert resets and resets[0] == "malformed", f"no reasoned withdrawal; events: {events}"
    assert any(s.kind in ("escalate", "retry") for s in agent.steps)
    last = len(events) - 1 - [k for k, _ in events][::-1].index("reset")
    assert "".join(t for k, t in events[last + 1:] if k == "token") == result["answer"]
