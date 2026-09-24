import { useMemo } from "react"
import type { Components } from "react-markdown"
import { AlertTriangle, BadgeCheck, BookOpen, Calculator, Code2, FileCheck2 } from "lucide-react"
import { Markdown } from "@/components/prompt-kit/markdown"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import { TIER } from "@/lib/tiers"
import type { Decision, Passage, Step, Turn, Verdict } from "@/lib/types"
import { cn } from "@/lib/utils"

// ---- Citations ---------------------------------------------------------------
// The backend normalises every citation to [Doc.md#N] and has already checked
// each one resolves to a passage it retrieved. Here they become pills, the way
// ChatGPT marks sources inline -- except these open the clause itself.

const CITE = /\[([\w.\-]+\.(?:md|pdf|txt)#\d+)\]/g

/** Rewrite citations as hash links a custom renderer can recognise. */
function linkCitations(text: string): string {
  return text.replace(CITE, (_, id: string) => `[${id}](#cite=${encodeURIComponent(id)})`)
}

/** "Maintenance_SOP_v7.md · §4.2 For Group 1…" → "§4.2" and "Maintenance SOP v7". */
export function citeParts(p: Passage | undefined, id: string) {
  const doc = id.split("#")[0].replace(/\.(md|pdf|txt)$/, "").replace(/[_-]+/g, " ")
  // Only numbered clauses make a useful label; "§EQUIPMENT" reads as noise,
  // so a named heading falls back to the document.
  const section = p?.cite.match(/§\s*(\d[\w.\-]*)/)?.[1]
  return { doc, section: section ? `§${section}` : null }
}

/** A retrieved passage rendered as markdown -- SOP clauses carry tables, and
 *  raw pipes are not readable. Shared with the Inspector's Sources tab. */
export function PassageText({ text, className }: { text: string; className?: string }) {
  const flowed = useMemo(() => unwrap(text), [text])
  return <Markdown className={cn("prose-passage", className)}>{flowed}</Markdown>
}

/** SOP sources are hard-wrapped at ~80 columns, and the markdown renderer
 *  turns every newline into a break, so passages read "additionally / require".
 *  Join wrapped prose lines; leave tables, lists and headings alone. */
function unwrap(text: string): string {
  // Tables, lists, headings, quotes -- and "Label: value" lines, which is how
  // the equipment register is written; joining those made one run-on line.
  const structural = /^\s*(\||[-*+]\s|\d+[.)]\s|#|>|[A-Z][\w ()/&-]{0,32}:\s)/
  const lines = text.split("\n")
  const out: string[] = []
  for (const line of lines) {
    const prev = out[out.length - 1]
    if (prev !== undefined && prev.trim() && line.trim()
        && !structural.test(prev) && !structural.test(line)) {
      out[out.length - 1] = `${prev.trimEnd()} ${line.trim()}`
    } else {
      out.push(line)
    }
  }
  return out.join("\n")
}

function CitationPill({ id, passage, onOpen }: { id: string; passage?: Passage; onOpen?: (id: string) => void }) {
  const { doc, section } = citeParts(passage, id)
  if (!passage) {
    // Should not survive verification; if it does, say so rather than hide it.
    return (
      <span title="This citation does not match any retrieved passage"
            className="mx-0.5 inline-flex items-center gap-1 rounded-md border border-bad/40 bg-bad/10 px-1.5 align-baseline text-[0.78em] font-medium text-bad">
        <AlertTriangle className="size-3" /> unresolved
      </span>
    )
  }
  return (
    <HoverCard openDelay={120} closeDelay={80}>
      <HoverCardTrigger asChild>
        {/* A button, not just a hover target: Radix hover cards are
            mouse-only, so clicking -- or Enter from the keyboard -- pins the
            clause in the Inspector instead. */}
        <button type="button" onClick={() => onOpen?.(id)}
                aria-label={`Source ${section ?? doc}, ${doc}. Open in the Inspector.`}
                className="mx-0.5 inline-flex max-w-[16rem] items-center gap-1 rounded-md bg-muted px-1.5 align-baseline text-[0.78em] font-medium text-muted-foreground transition-colors hover:bg-brand/15 hover:text-brand focus-visible:bg-brand/15 focus-visible:text-brand">
          <BookOpen className="size-3 shrink-0" />
          <span className="truncate">{section ?? doc}</span>
          {section && <span className="hidden truncate opacity-70 sm:inline">· {shortDoc(doc)}</span>}
        </button>
      </HoverCardTrigger>
      <HoverCardContent side="top" align="start" className="w-96 max-w-[90vw] p-0">
        <div className="border-b px-3.5 py-2.5">
          <div className="flex items-center gap-2 text-xs font-medium">
            <BookOpen className="size-3.5 text-brand" />
            <span className="truncate">{doc}</span>
            <span className="ml-auto font-mono text-muted-foreground">#{id.split("#")[1]}</span>
          </div>
          {passage.cite.includes("·") && (
            <div className="mt-1 truncate text-xs text-muted-foreground">
              {passage.cite.split(" · ").slice(1).join(" · ")}
            </div>
          )}
        </div>
        <div className="max-h-64 overflow-auto px-3.5 py-3">
          <PassageText text={passage.text} />
        </div>
        {onOpen && (
          <div className="border-t px-3.5 py-2 text-xs text-muted-foreground">
            Click to open in the Inspector
          </div>
        )}
      </HoverCardContent>
    </HoverCard>
  )
}

function shortDoc(doc: string) {
  // "Maintenance SOP v7" → "SOP v7"; keeps the pill short where a code exists.
  const m = doc.match(/\b(SOP|IP|ER)[\s-]?v?\d*/i)
  return m ? m[0] : doc.split(" ").slice(0, 2).join(" ")
}

export function AnswerBody({ text, evidence, onCite }: {
  text: string
  evidence: Passage[]
  onCite?: (id: string) => void
}) {
  const byId = useMemo(() => new Map(evidence.map((p) => [p.id, p])), [evidence])
  const components: Partial<Components> = useMemo(() => ({
    a({ href, children, ...rest }) {
      if (href?.startsWith("#cite=")) {
        const id = decodeURIComponent(href.slice(6))
        return <CitationPill id={id} passage={byId.get(id)} onOpen={onCite} />
      }
      return <a href={href} target="_blank" rel="noreferrer" {...rest}>{children}</a>
    },
  }), [byId, onCite])
  const linked = useMemo(() => linkCitations(text), [text])
  return <Markdown className="prose-answer" components={components}>{linked}</Markdown>
}

// ---- The verification seal ---------------------------------------------------
// None of the reference products shows why an answer should be trusted. Every
// line here comes from a check the backend actually ran.

const FAILURE: Record<string, string> = {
  uncited: "No citation backs this answer.",
  "invented-citation": "A citation does not match anything retrieved.",
  "fabricated-output": "Reported program output the sandbox never printed.",
  ungrounded: "The knowledge base returned nothing for this.",
  "sandbox-failed": "No sandbox run succeeded.",
  malformed: "The model returned a tool call instead of an answer.",
  truncated: "The model ran out of room before answering.",
  "step-limit": "Stopped at the step limit before finishing.",
  empty: "No answer was produced.",
  failed: "The task failed.",
}

export function Seal({ turn }: { turn: Turn }) {
  const v = turn.verdict as Verdict | null
  if (!v) return null
  if (v !== "ok") {
    return (
      <div className="mt-3 flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-[13px]">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />
        <span><span className="font-medium">Not verified.</span> {FAILURE[v] ?? v} Treat with care.</span>
      </div>
    )
  }
  const checks = verifiedChecks(turn.steps, turn.evidence.length, turn.deliverables.length)
  if (!checks.length) return null
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ok">
      <BadgeCheck className="size-4" />
      {checks.map(({ icon: Icon, text }) => (
        <span key={text} className="inline-flex items-center gap-1">
          <Icon className="size-3.5 opacity-80" /> {text}
        </span>
      ))}
    </div>
  )
}

function verifiedChecks(steps: Step[], evidence: number, deliverables: number) {
  const tools = steps.filter((s) => s.kind === "tool").map((s) => s.label)
  const out: { icon: typeof BookOpen; text: string }[] = []
  const cited = steps.some((s) => s.kind === "verify" && s.label === "checks passed"
                               && Number(s.detail.citations) > 0)
  if (evidence && cited) {
    const n = Number(steps.find((s) => s.kind === "verify" && s.label === "checks passed")?.detail.citations ?? 0)
    out.push({ icon: BookOpen, text: `${n} citation${n === 1 ? "" : "s"} resolved` })
  }
  if (tools.includes("calculate") || tools.includes("percent_change")) {
    out.push({ icon: Calculator, text: "numbers computed, not generated" })
  }
  if (tools.includes("run_python")) out.push({ icon: Code2, text: "checked in the sandbox" })
  if (deliverables) out.push({ icon: FileCheck2, text: "read back from the document" })
  return out
}

// ---- The routing chip --------------------------------------------------------

export function RouteChip({ decision }: { decision: Decision | Record<string, never> }) {
  if (!("tier" in decision)) return null
  const t = TIER[decision.tier]
  return (
    <HoverCard openDelay={150}>
      <HoverCardTrigger asChild>
        <span tabIndex={0}
              className={cn("inline-flex h-6 cursor-default items-center gap-1 rounded-md px-1.5 font-mono text-[11px] font-semibold", t.tone)}>
          {decision.tier}
          <span className="font-sans font-medium">{t.name}</span>
        </span>
      </HoverCardTrigger>
      <HoverCardContent side="top" align="start" className="w-72 text-sm">
        <p className="text-muted-foreground">{decision.why}</p>
        <p className="mt-1.5 truncate font-mono text-xs text-muted-foreground">
          {decision.model_name ?? `tool: ${decision.tool}`}
        </p>
      </HoverCardContent>
    </HoverCard>
  )
}
