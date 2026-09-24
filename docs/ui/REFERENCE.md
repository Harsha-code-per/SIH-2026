# Interface reference — what Claude, ChatGPT and Gemini do

Studied live on 24 September 2026, in the user's own signed-in browser, to
ground the redesign in how these products actually behave today rather than
how they are remembered. **Only layout and behaviour were recorded — no
conversation content.**

Read this before changing the interface. The design decisions in
`docs/ROADMAP.md` phase 2b trace back to what is written here.

---

## The shape all three share

This is the convention people arrive already knowing. Deviate from it only for
a reason.

| Element | Convention |
|---|---|
| **Left sidebar** | ~210–260px. Logo and a collapse toggle at the top; New chat; Search; a few nav items; a history list |
| **History items** | One line, truncated with an ellipsis. The active item is highlighted; a `⋯` menu appears on hover |
| **Account** | At the **foot** of the sidebar: avatar initials, name, plan, a settings affordance |
| **Main header** | Minimal. At most the conversation title (Claude, with a rename dropdown), Share, and `⋯`. ChatGPT and Gemini show no title |
| **Empty state** | A greeting and the composer, centred vertically. ChatGPT adds one suggestion beneath |
| **Reading column** | **~540–600px**, centred. Deliberately narrow for line length |
| **User messages** | Right-aligned in a soft bubble. Claude: rounded rectangle. ChatGPT and Gemini: pill |
| **Assistant replies** | **Unboxed, no avatar**, full-column markdown. Headings, bold lead-ins, lists |
| **Action row** | Under each reply: copy, thumbs up/down, retry, share, `⋯`. Quiet until needed |
| **Composer** | Rounded; attach (`+`) on the left; **model picker inside the composer**; voice on the right; a one-line disclaimer beside it |
| **Scroll** | A floating scroll-to-bottom button above the composer |

## What is distinctive to each

### Claude
- **Tool use as progressive disclosure, inline in the thread.** One quiet line
  — "Read 7 files, ran 6 commands, and 6 more tools ›" — expands to a bordered
  list. Each row is a verb and its argument: "Searched the web · *query*",
  "Ran a command", "Checking … · `SKILL.md`". Each row expands again. Three
  levels, and the thread stays readable at the first.
- **Reasoning summarised** as one-line entries ("Weighing candidate names for
  the workbench ›") in the same list.
- **Deliverables as file cards**: an icon, the file name, the type
  ("Presentation · PPTX"), and a split Download button.
- **Serif body type** for replies; warm near-black palette.
- The model picker sits beneath the composer beside the disclaimer.

### ChatGPT
- **Citations as small grey pills inline in the sentence**, carrying the source
  name.
- A **Sources** button closes each answer. It opens a **~310px right panel that
  pushes the conversation aside** rather than covering it, grouped by kind with
  counts ("Files · 1", "Web · 1405"). Each entry: site, bold title, date.
- A "Think" toggle inside the pill composer.
- Pure black palette, sans throughout.

### Gemini
- **One expressive touch**: a soft radial glow behind the empty state. It is
  gone once the conversation starts.
- A model picker inside the pill composer ("Flash Extended").
- Sans throughout, hollow-circle bullets.

## What none of them do

This is the opening, and every item traces to something this backend already
does:

1. **None shows whether an answer was verified.** Ours checks every citation
   resolves, reads the generated document back, and checks reported program
   output against what the sandbox printed. → **a verification seal on each
   reply.**
2. **None explains why a model was chosen** — all three hand the user a picker.
   Ours routes automatically and can say why. → **"Auto · L2" in the composer,
   previewing as you type, with the reason on hover.**
3. **None can show data sovereignty**, because all three are cloud services. →
   **an always-visible containment indicator**, green only when the backend
   says `contained`.

## Decisions taken from this study

- Adopt the shared shape wholesale; it is what users expect.
- Reasoning **inline** as Claude does: a summary line that expands to the
  routing, every step, the code it ran and what came back, and the model's own
  reasoning. It first also lived in a right-hand Inspector; showing it twice
  was redundant, so the right panel now holds only the evidence — sources,
  files, containment — and opens on request (D-66).
- The right panel **pushes** content, as ChatGPT's Sources panel does.
- Citations as **inline pills**, with a hover card showing the passage.
- Deliverables as **file cards**.
- **Sans**, not Claude's serif: tags like `P-204` and readings with aligned
  figures read better for engineering content.
- **Warm neutral dark** plus a light theme; Gemini's ambient glow on the empty
  state only; motion only where it tells the user something.
- The model picker is replaced by **visible auto-routing** — the problem
  statement asks for automatic selection, so the composer shows it happening.
