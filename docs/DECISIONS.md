# Decision log

Why the code is the way it is. Most entries record something discovered by
running the system, not by reading it — and would be rediscovered the hard way
by anyone who did not know.

**Before changing any behaviour described here, read its entry.** Several look
like simplifications waiting to happen and are in fact fixes for bugs that only
appear under load, air-gapped, or in a fresh clone.

Format: what we decided · why · where it lives.

---

## Architecture

### D-1 · Deterministic routing, not an LLM classifier
Routing is regex features matched against ordered rules in `models.yaml`. No
model call sits in the hot path.
**Why:** routing must be explainable to a judge and reproducible in a test. An
LLM classifier would be slower, non-deterministic, and cost a model call before
any work begins.
**Where:** `app/router.py`, `models.yaml`, `tests/test_router.py`.

### D-2 · Open-weight models only; NVIDIA NIM rather than OpenRouter
**Why:** the problem statement's own title says "Open-Weight". NIM serves open
weights and is the same container that deploys on-premise, so "identical
weights, identical serving stack, currently pointed at a hosted endpoint" is
literally true. OpenRouter would have been acceptable only if pinned to
open-weight models — never GPT, Claude or Gemini.
**Where:** `models.yaml`.

### D-3 · No agent framework
A plain tool-calling while-loop.
**Why:** it is about a hundred lines and debuggable. Every bug in this log was
found by reading a trace of that loop; a framework puts the control flow in
someone else's repository.
**Where:** `app/agent.py`.

### D-4 · No vector database
Retrieval is a numpy dot product over an in-memory array.
**Why:** a few hundred chunks do not justify a service that needs its own
container, backup and air-gapping. The ceiling is marked with a `ponytail:`
comment; move to `sqlite-vec` past ~50k chunks (roadmap F9).
**Where:** `app/kb.py`.

### D-5 · The vision model reads; the reasoning model reasons
When a task involves an image, the conversation stays with a tool-capable model
and the vision model is called *by the tools*.
**Why:** routing an image task sent the whole conversation to
`llama-3.2-11b-vision`, which cannot do tool calling. It printed a JSON tool
call as its final answer, and verification passed it. The trace now reads
"LV2 reads · L2 reasons".
**Where:** `app/agent.py::run`, `app/router.py::orchestrator`.

### D-6 · Model strength follows the escalation chain
`orchestrator()` picks the tool-capable tier nothing escalates past.
**Why:** the first version inferred strength from the order routing rules
happened to appear in, and chose the cheap tier.
**Where:** `app/router.py::orchestrator`.

---

## Containment

### D-7 · Enforce with Docker, not nftables
The app sits on a network marked `internal: true`, so it has no default route.
A gateway container is the only thing on both networks and forwards one
destination.
**Why:** the original nftables rules hooked `forward`, which only sees traffic
routed *between* interfaces. On a host they installed cleanly and enforced
nothing. They also needed root. The Docker approach needs neither, and is
stronger: the internet is not blocked, it is unroutable.
**Where:** `docker-compose.yml`, `egress/proxy.conf`. `egress/sentinel.sh`
remains as an optional host-level belt.

### D-8 · "Contained" requires enforcement, observation and zero leaks
**Why:** once `tcpdump` was installed the flag went green on its own — nothing
had leaked, but nothing was stopping anything either. A machine that makes no
outbound calls looks identical to one that cannot. Enforcement is *detected*
(by reading `/proc/net/route`), never assumed.
**Where:** `app/egress.py::snapshot`, `tests/test_sovereignty.py`.

### D-9 · A connection that got out uninvited is LEAKED, never ALLOWED
**Why:** the first tripwire succeeded against a non-allowlisted host and was
labelled `ALLOWED` — benign yellow in the interface, for the worst case the
system exists to prevent.
**Where:** `app/egress.py::_classify`.

### D-10 · Gateway resolves upstreams at request time
nginx uses Docker's embedded DNS with a variable in `proxy_pass`.
**Why:** nginx exits if an upstream name does not resolve at startup, and the
app and gateway depend on each other. Restarting the app killed the gateway
with "host not found in upstream".
**Where:** `egress/proxy.conf`.

### D-11 · TLS passthrough, not termination
**Why:** the gateway moves bytes for one name. It never sees plaintext or holds
a key, and certificates are still validated end to end against the real host.
**Where:** `egress/proxy.conf` (`stream` block).

### D-12 · Ship every model in the image; fetch nothing at runtime
**Why:** fastembed downloads weights on first use. With no route out, every
search failed and the run carried on, writing a document with nothing behind
it. Baking at build time turns a silent runtime failure into a loud build one.
**Where:** `Dockerfile`.

### D-13 · The interface loads zero external resources
**Why:** an air-gapped workbench that fetches a CDN stylesheet undermines its
own claim, and the request would show up in the egress monitor as noise.
**Where:** `static/index.html`.

---

## Correctness

### D-14 · Arithmetic never touches a model, and never uses eval
`calculate` walks the AST against an operator whitelist.
**Why:** a number in an engineering document must be computed, not generated.
`eval` would hand a crafted expression to the interpreter. Tested with hostile
inputs.
**Where:** `app/tools.py::calculate`, `tests/test_arithmetic.py`.

### D-15 · Floating-point noise is removed before anyone reads it
**Why:** `8.2 - 7.1` is `1.0999999999999996` in IEEE 754 — correct, and
unusable in a document a section head signs. Results are tidied to twelve
significant digits, far beyond any instrument here.
**Where:** `app/tools.py::_tidy`.

### D-16 · Verification reads the generated document back
**Why:** when a document is produced, the chat reply is a receipt ("note
created") and the sources are inside the file. Demanding citations in the reply
failed properly sourced notes.
**Where:** `app/agent.py::_verify`, `_docx_text`.

### D-17 · Citations are recognised in every bracket style
ASCII `[x]`, CJK `【x】`, full-width, parentheses, and bare `Doc.md#7`.
**Why:** the model emits CJK brackets. A correct, well-cited answer was marked
uncited and escalated for nothing. Separately, `write_docx` wrote unbracketed
source lines that were not recognised at all.
**Where:** `app/agent.py::_CITE`, `app/tools.py::write_docx`.

### D-18 · Program output the model reports is checked against real stdout
**Why:** one coding run presented intercept `5.9` and month `5.44` in a fenced
"Output from the script" block. The sandbox had printed `6.47` and `4.44`. A
fabricated number that looks computed carries the authority of a real one.
**Where:** `app/agent.py::unbacked_output`, `tests/test_output_fidelity.py`.

### D-19 · A task that searched and found nothing is ungrounded
**Why:** verification skipped the citation check when there was no evidence,
so the less a run retrieved, the easier it passed — which inverted the check.
**Where:** `app/agent.py::_verify`.

### D-20 · A code task with zero successful sandbox runs is not verified
**Why:** six timed-out sandbox runs produced `verdict: ok` because nothing
contradicted the prose. One failure then a fix is the loop working; zero
successes is not.
**Where:** `app/agent.py::_verify`.

---

## The agent loop

### D-21 · Loop guards are general, and they remove tools rather than ask
Identical calls are detected by a key-order-insensitive signature. After two
repeats the looping tools are withdrawn; after four, tool use is disabled.
**Why:** given a search tool, the model rephrased the same query until the
budget was gone. A search-specific guard just moved the loop to `calculate`.
And asking a model to stop looping does not reliably stop it — removing the
option does.
**Where:** `app/agent.py`, `REPEATS_BEFORE_WITHDRAWAL`.

### D-22 · Token budgets are per model, and an exhausted turn gets more room
**Why:** these are reasoning models. At 1536 tokens the whole budget went on
reasoning with none left to emit the tool call: `finish_reason: length`, empty
content, no calls. That is an exhausted turn, not an empty answer.
**Where:** `models.yaml` (`max_tokens`), `app/agent.py`.

### D-23 · At the top tier, repair in place
**Why:** with nowhere to escalate, a flawed result was handed back as-is. A
repairable verdict now retries once with an instruction naming what to fix.
**Where:** `app/agent.py::REPAIRABLE`.

### D-24 · Route on the conversation, not the latest words
**Why:** "and the temperature?" carries none of the signal its first turn did,
and would drop to the cheap tier mid-analysis.
**Where:** `app/agent.py::run`.

### D-25 · Engineering questions go to L2 however short they are
A measurement with a unit, an equipment tag, or words like zone, limit or
threshold reach the analysis tier.
**Why:** "what zone is 8.2 mm/s?" reads like chat and needs the SOP. Routed to
L1 it took 155 seconds. Now 6.
**Where:** `app/router.py::_ANALYZE`.

---

## Retrieval

### D-26 · Index section headings, and weight them above prose
**Why:** clause numbers — `4.2`, `ISO 10816-3`, `MRPL-QA-12` — live in
headings, and only bodies were indexed. The identifiers an engineer searches by
were absent from the index entirely. Heading weighting then made "clause 4.2"
return clause 4.2 rather than the later clause that mentions it.
**Where:** `app/kb.py::Chunk.searchable`, `HEADING_BOOST`.

### D-27 · Hybrid BM25 + dense, blended at α = 0.7
**Why:** dense vectors treat rare identifiers as unremarkable tokens. 0.7 is the
only value on the thirteen-query set that retrieves every expected passage in
the top five. Lexical-heavy settings win more first places but drop a passage
entirely, and the agent reads the whole result set.
**Where:** `app/kb.py::DEFAULT_ALPHA`, `tests/test_retrieval.py`.

### D-28 · The tokeniser keeps dots and hyphens inside identifiers
**Why:** splitting `4.2` into `4` and `2`, or `P-204` into `p` and `204`,
destroys the identifiers before scoring ever happens.
**Where:** `app/kb.py::_TERM`.

---

## Documents and vision

### D-29 · Decide whether a model is needed before choosing one
A PDF with a text layer is read directly; only pages without one go to the
vision model.
**Why:** a digital PDF already carries its text, and a vision model over it is
slower and less accurate.
**Where:** `app/ocr.py`.

### D-30 · Classify an attachment from the file, never the prompt
**Why:** guidance text appended to the prompt contained the word "drawing",
the router matched it, and a scanned report went to the drawing model.
**Where:** `app/ocr.py::classify_attachment`.

### D-31 · Transcription is cached by content hash
**Why:** 48 seconds per page, deterministic, and repeated on every run —
including every demonstration. Keyed on the file's hash so an edit invalidates.
**Where:** `app/tools.py::parse_page`, `tests/test_cache.py`.

### D-32 · Drawings are read in overlapping tiles, concurrently
**Why:** a full sheet downscales a tag to a few pixels (4 of 9 read). Tiles fix
that; overlap keeps a tag on a seam whole; concurrency took a sheet from 365s
to 12s.
**Where:** `app/tools.py::_tiles`, `describe_image`.

### D-33 · Degenerate vision output is detected and dropped
**Why:** a tile lost its place and counted `V-102` to `V-329` from a sheet with
one vessel. Perfect recall, worthless precision — and an invented tag is worse
than a missing one. Six consecutive numbers under one prefix, or mostly
repeated lines, triggers a retry and then a named gap in the output.
**Where:** `app/tools.py::_looks_degenerate`, `tests/test_drawing.py`.

### D-34 · Tell the vision model how ISA-5.1 instrument bubbles are drawn
**Why:** a bubble puts function letters above the loop number. Read literally
that is two fragments, and every instrument on the sheet was lost.
**Where:** `app/tools.py::describe_image` prompt.

### D-35 · `nemotron-parse-2.0` rejected for the document tier
**Why:** it expects its own request shape; over chat-completions it emitted
"to" several hundred times, then 502'd. The omni model transcribes verbatim
with tables intact. A parser client is finale work.
**Where:** `models.yaml`, `docs/model-benchmark.md`.

---

## Platform and operations

### D-36 · Sandbox code goes over stdin, not a bind mount
**Why:** when the app runs in a container and talks to the host's Docker
daemon, a mount path resolves on the host, where the app's temp directory does
not exist. stdin has no path to get wrong.
**Where:** `app/tools.py::run_python`.

### D-37 · `docker-cli`, not `docker.io`
**Why:** Debian 13 split the packages. `docker.io` now ships only `docker-init`.
The app had no `docker` binary and every sandbox call timed out.
**Where:** `Dockerfile`.

### D-38 · The app runs as the invoking user
**Why:** a root container wrote cache files and documents into the bind-mounted
`data/` that the person who started the stack could not delete.
**Where:** `docker-compose.yml` (`user:`), `Makefile`.

### D-39 · Tokens are signed, not stored
HMAC-signed with a per-deployment key, carrying a per-user version.
**Why:** tokens in memory meant every restart signed everybody out. The version
means a password or role change invalidates old tokens instead of letting a
demoted user keep their old role until expiry.
**Where:** `app/auth.py`, `tests/test_auth.py`.

### D-40 · The first admin password is generated, never fixed
**Why:** a fixed default is a back door in every deployment.
**Where:** `app/auth.py::_seed`.

---

## Things that broke the tests themselves

### D-41 · Tests are collected, never run from `__main__`
**Why:** each test file ran itself from a `__main__` block at the bottom.
Anything appended after that block was defined after the runner had finished,
so it never ran and the file still reported success. **14 of 71 tests had never
run, including four sovereignty checks.**
**Where:** `tests/run.py`.

### D-42 · `_emit`'s parameters are positional-only
**Why:** detail comes from tool payloads that may contain `kind` or `label`.
Python binds a keyword to a parameter *before* the function body runs, so a
guard inside the function could never help. The `/` in the signature does.
**Where:** `app/agent.py::_emit`.

### D-43 · A class setting `display` overrides the `hidden` attribute
**Why:** the sign-in overlay stayed on screen while every piece of state behind
it said signed in. `.gate[hidden]{display:none}` fixes it; watch for this on
any element that has both.
**Where:** `static/index.html`.

### D-44 · Secrets are checked by path, not only by content
`scripts/check-secrets.sh` runs as a pre-commit hook; `make up` installs it.
**Why:** `data/secret.key` — the token signing key — was committed and pushed.
The check at the time grepped diffs for `nvapi-`, which a binary key file does
not contain. Anything under `data/` outside a short allowlist is now refused as
runtime state. The key was rotated; history was not rewritten, since that needs
a force-push over a shared remote and rotation already makes the old key
worthless. **Never trust the key in commit `f1c3c20`.**
**Where:** `scripts/check-secrets.sh`, `.gitignore`.

### D-45 · A pattern beginning with `-` needs `grep -e`
**Why:** the private-key pattern starts with `-----`, grep read it as an
option, the check failed silently, and the script still printed "clean". Each
check in `check-secrets.sh` has a negative control proving it fires.
**Where:** `scripts/check-secrets.sh`.

---

## Environment facts worth knowing

- **The NIM key has a trailing hyphen**, and it is part of the key (64
  characters after `nvapi-`). Without it, completions return 403 while
  `/v1/models` still returns 200 — which is misleading.
- **Only 11 of 81 catalogued NIM models accept completions on this key.**
  `/v1/models` lists the catalogue, not your entitlement. Run
  `make verify-models`, and sweep for completions before trusting a model id.
- **Hosted latency inverts the tier ordering** — the 3B-active model is slower
  than the 12B-active one on shared infrastructure.
- **The Chrome automation extension reports screenshots at a different scale
  from the page viewport.** Pass coordinates from the screenshot; verify with
  `document.elementFromPoint` when a click seems to do nothing.
