# Playbook: run the demo

The order, what to say, and what to expect. Timings are measured on the hosted
endpoint and vary with its load.

## Before you record

Do these the day of, not the week before.

```bash
git pull && make up                   # current code, contained stack
make verify-models                    # every model id still resolves
make test                             # 109 passing
make prove                            # no default route; tripwire blocked
```

**Warm the caches.** The first scanned-page read takes ~48s and the first
drawing ~12s; repeats are instant. Run the scanned-report and P&ID tasks once
before recording, or the video will contain a long wait.

**Sign in beforehand**, and use a clean conversation (**New conversation**).

**Close other tabs and notifications.** Screen-record at 1920×1080.

## The sequence — about five minutes

| # | Action | Shows | Expect |
|---|---|---|---|
| 1 | Header: point at **EGRESS contained** | containment is live, not claimed | instant |
| 2 | Preset **Percentage change** | L0 — arithmetic never touches a model | ~0.1s, `26.1538%` |
| 3 | Type: *Pump P-204 drive-end vibration is 8.2 mm/s RMS. What zone is that?* | routing to L2, retrieval, citation | ~6s, "Zone D" with `[Maintenance_SOP_v7.md#7]` |
| 4 | Follow up: *And who has to approve it?* | multi-turn memory | Section Head and Head of Maintenance |
| 5 | Attach `Inspection_Report_P-204.pdf`, ask for findings against the SOP | scanned PDF, no text layer → vision | trace shows `attachment · page`, `LV` |
| 6 | Ask for an approval note as a Word document | the flagship workflow | `.docx` with six sections and citations; **open it** |
| 7 | Preset **Trend in sandbox** | code written, run with no network, checked | sandbox exit 0 · `--network none` |
| 8 | Attach `PID_CDU_P-204.png`, identify the tags | drawing understanding | "LV2 reads · L2 reasons", tags listed |
| 9 | **Attempt external call** | the tripwire | `BLOCKED` in ~1ms |
| 10 | Models tab: point at the registry and the sovereign column | one config change to local | — |

## What to say at each point

- **1.** "This badge only turns green when three things are true — and I'll
  prove the most important one at the end."
- **2.** "Arithmetic doesn't go to a language model. A number in an engineering
  document is computed, not generated."
- **3.** "It picked the reasoning tier because this has to be checked against
  the SOP. And the citation points at the exact clause."
- **6.** "It reads the note back after writing it, and fails its own check if a
  citation doesn't resolve to something it actually retrieved."
- **7.** "The code runs in a container with no network at all, and if the model
  reports output the sandbox didn't print, that fails too."
- **9.** "It can't reach the internet. Not blocked — unroutable. It can't even
  resolve the name."
- **10.** "Today the models are hosted open weights. Going fully local is this
  column — a configuration change, not a rewrite."

## If something goes wrong

- **A task is slow** — the hosted endpoint is shared. Keep talking about the
  trace; it is the interesting part anyway.
- **503** — the client retries and falls back a tier automatically.
- **A verdict other than `ok`** — say so. "It caught its own mistake" is a
  better demo than a hidden one.

## Say the limitations out loud

Inference is hosted today. Drawing reading gets 7 of 9 tags on the test sheet.
Both are in `docs/ROADMAP.md`. Saying them first makes every other claim more
credible.
