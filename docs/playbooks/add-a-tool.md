# Playbook: add a tool

Give the agent a new capability. Tools live in `app/tools.py`.

## 1. Write the function

```python
def write_pptx(title: str, slides: list[dict], filename: str = "Deck.pptx") -> dict:
    """One line saying what it does -- the model reads this."""
    ...
    return {"path": str(dest.relative_to(ROOT)), "bytes": ...,
            "download": f"/api/download/{dest.name}"}
```

Rules, each from a real bug:

- **Return a dict.** Errors are raised and `T.call` turns them into
  `{"error": ...}` for the model to correct — that retry is the point of a loop.
- **Validate any path a model supplies.** Resolve it and refuse anything outside
  `data/`: `if not p.is_relative_to(ROOT / "data"): raise ValueError(...)`.
- **Never touch the network.** Nothing in `tools.py` may make an outbound call
  except through `_ask_vision`, which goes to the configured model endpoint.
- **Accept the keys models actually send**, not only the ones you named. Models
  wrote `content` where the schema said `body`, and the text was silently
  dropped (D-17). Accept aliases; raise on a shape you cannot use.
- **Anything expensive and deterministic gets cached** by content hash — see
  `parse_page` and `_cache_key`.
- **Never compute a number with a model.** Call `calculate`.

## 2. Register it

At the bottom of `app/tools.py`:

```python
TOOLS["write_pptx"] = _t("write_pptx",
    "Produce a PowerPoint deliverable. Each slide has a title and bullets.",
    {"title": {"type": "string"},
     "slides": {"type": "array", "items": {"type": "object"}},
     "filename": {"type": "string"}},
    ["title", "slides"], write_pptx)
```

The description is the model's only documentation. Say what to use it for and
what shape the arguments take.

## 3. Wire deliverables into verification

If the tool writes a file, add its name to the deliverables branch in
`app/agent.py::_converse` (it checks `name in ("write_docx", "write_xlsx")`),
and teach `_docx_text` — or a sibling — to read that format back. Verification
checks **what was written**, not what the model said it wrote (D-16).

## 4. Surface it in the trace

If the tool's result is worth seeing, add a branch in `_converse` that emits a
readable `result` step. Otherwise it shows as its own name with truncated
output, which is acceptable.

## 5. Test it

Add tests to the relevant file in `tests/`. At minimum: a normal call works, a
malformed argument is refused with a useful message, a path outside `data/` is
refused. Run `make test`.

## 6. Run it for real

```bash
make restart
```

Ask for something that needs the tool, watch the trace, open the output. Most
bugs in `docs/DECISIONS.md` passed their unit tests and failed the first real
run.
