import { useState } from "react"
import {
  AlertTriangle, ArrowRightLeft, BookOpen, BrainCircuit, Calculator, CheckCircle2,
  ChevronDown, Code2, FileSpreadsheet, FileText, RefreshCw, ScanLine, Search, Sparkles, Zap,
} from "lucide-react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { TextShimmer } from "@/components/prompt-kit/text-shimmer"
import { currentActivity, describe, summarise } from "@/lib/steps"
import { TIER } from "@/lib/tiers"
import type { Decision, Step } from "@/lib/types"
import { cn } from "@/lib/utils"

// Icons tell the kinds of work apart; colour is kept for status.
const NEUTRAL = "text-muted-foreground bg-muted ring-border"
const TOOL: Record<string, { icon: typeof Search; tone: string }> = {
  kb_search:      { icon: Search,          tone: NEUTRAL },
  read_document:  { icon: BookOpen,        tone: NEUTRAL },
  parse_page:     { icon: ScanLine,        tone: NEUTRAL },
  describe_image: { icon: ScanLine,        tone: NEUTRAL },
  calculate:      { icon: Calculator,      tone: NEUTRAL },
  percent_change: { icon: Calculator,      tone: NEUTRAL },
  run_python:     { icon: Code2,           tone: NEUTRAL },
  write_docx:     { icon: FileText,        tone: NEUTRAL },
  write_xlsx:     { icon: FileSpreadsheet, tone: NEUTRAL },
}

/** The agent's work, inline under the answer the way Claude shows it: one
 *  line that says what was done, opening onto every step, the code it ran,
 *  what came back, and the model's own reasoning. */
export function Reasoning({ steps, decision, thinking, live = false, thinkingNow = false }: {
  steps: Step[]
  decision?: Decision | Record<string, never> | null
  thinking?: string
  live?: boolean
  thinkingNow?: boolean
}) {
  // Open while it runs, so the work is watched as it happens; a finished turn
  // folds to its summary line.
  const [open, setOpen] = useState(live)
  const trail = pair(steps)
  if (!trail.length && !live && !thinking) return null

  const route = decision && "tier" in decision ? decision as Decision
    : steps.find((s) => s.kind === "route" && s.detail.tier)?.detail as unknown as Decision | undefined
  const seconds = steps.length > 1 ? Math.round(steps[steps.length - 1].ts - steps[0].ts) : 0

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mb-3">
      <CollapsibleTrigger className="group/trigger inline-flex max-w-full items-center gap-2 rounded-full border border-border/70
                                     bg-card py-1 pl-1.5 pr-3 text-[13px] text-muted-foreground
                                     transition-colors hover:bg-accent hover:text-foreground">
        <span className={cn("grid size-6 shrink-0 place-items-center rounded-full",
                            live ? "bg-brand text-brand-foreground" : "bg-muted text-foreground")}>
          {live ? <Sparkles className="size-3.5 animate-pulse" /> : <BrainCircuit className="size-3.5" />}
        </span>
        <span className="min-w-0 truncate">
          {live
            ? <TextShimmer>{thinkingNow ? "Thinking…" : currentActivity(steps)}</TextShimmer>
            : summarise(steps)}
        </span>
        {!live && seconds > 0 && <span className="tabular shrink-0 opacity-70">· {seconds}s</span>}
        <ChevronDown className="size-3.5 shrink-0 transition-transform group-data-[state=open]/trigger:rotate-180" />
      </CollapsibleTrigger>

      <CollapsibleContent className="data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down overflow-hidden">
        <div className="relative ml-[18px] mt-3 space-y-3 border-l border-border pl-5">
          {route && (
            <div className="text-[13px]">
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn("rounded-md px-1.5 py-0.5 font-mono text-[11px] font-semibold", TIER[route.tier]?.tone)}>
                  {route.tier}
                </span>
                <span className="font-medium">{TIER[route.tier]?.name}</span>
                <span className="text-muted-foreground">
                  {route.rule === "manual" ? "· chosen by you" : `· rule ${route.rule}`}
                </span>
              </div>
              <p className="mt-1 text-muted-foreground">{route.why}</p>
              <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground/80">
                {route.model_name ?? `tool: ${route.tool}`}
              </p>
            </div>
          )}

          {trail.map(({ step, result }) => {
            const { verb, arg } = describe(step)
            const t = step.kind === "tool" ? TOOL[step.label] : null
            const Icon = t?.icon ?? (step.kind === "verify" ? (step.label === "checks passed" ? CheckCircle2 : AlertTriangle)
              : step.kind === "escalate" || step.kind === "retry" ? RefreshCw
              : step.kind === "route" ? ArrowRightLeft
              : step.kind === "error" ? AlertTriangle : Zap)
            const tone = t?.tone
              ?? (step.kind === "error" ? "text-bad bg-bad/12 ring-bad/25"
                : step.kind === "verify" ? (step.label === "checks passed" ? "text-ok bg-ok/12 ring-ok/25" : "text-warn bg-warn/12 ring-warn/25")
                : step.kind === "escalate" || step.kind === "retry" ? "text-warn bg-warn/12 ring-warn/25"
                : "text-muted-foreground bg-muted ring-border")
            const out = result ? describe(result) : null
            const stdout = typeof result?.detail.stdout === "string" ? result.detail.stdout.trim() : ""
            return (
              <div key={`${step.n}-${step.kind}`} className="relative text-[13px]">
                <span className={cn("absolute -left-[33px] top-0 grid size-6 place-items-center rounded-full ring-1 bg-background", tone)}>
                  <Icon className="size-3.5" />
                </span>
                <div className="pt-0.5">
                  <span className="font-medium text-foreground/90">{verb}</span>
                  {arg && <span className="break-words text-muted-foreground"> · {arg}</span>}
                </div>
                {step.label === "run_python" && typeof step.detail.arguments === "string" && (
                  <pre className="mt-1.5 max-h-48 overflow-auto rounded-lg border bg-muted/50 p-2.5 font-mono text-[11px] leading-relaxed">
                    {code(step.detail.arguments)}
                  </pre>
                )}
                {stdout ? (
                  <pre className="mt-1.5 max-h-40 overflow-auto rounded-lg border bg-muted/50 p-2.5 font-mono text-[11px]">
                    {stdout}
                  </pre>
                ) : out && (out.arg || result?.detail.error) ? (
                  <div className="mt-0.5 break-words text-xs text-muted-foreground">→ {out.arg ?? out.verb}</div>
                ) : null}
              </div>
            )
          })}

          {thinking && <Thought text={thinking} live={live} />}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

function Thought({ text, live }: { text: string; live: boolean }) {
  return (
    <div className="relative text-[13px]">
      <span className="absolute -left-[33px] top-0 grid size-6 place-items-center rounded-full bg-background text-brand ring-1 ring-brand/25">
        <BrainCircuit className="size-3.5" />
      </span>
      <div className="pt-0.5 font-medium text-foreground/90">{live ? "Thinking" : "Reasoning"}</div>
      {/* column-reverse keeps the newest thought in view while it streams */}
      <div className={cn("mt-1.5 flex max-h-56 overflow-auto rounded-lg bg-muted/40 p-3",
                         live ? "flex-col-reverse" : "flex-col")}>
        <p className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
          {live ? text.slice(-3000) : text}
        </p>
      </div>
    </div>
  )
}

/** Steps worth showing, each tool call joined to the result that answered it. */
function pair(steps: Step[]): { step: Step; result?: Step }[] {
  const out: { step: Step; result?: Step }[] = []
  for (const s of steps) {
    if (s.kind === "route" && s.detail.tier) continue      // shown as the routing row
    if (s.kind === "done") continue
    if (s.kind === "result") {
      const last = out[out.length - 1]
      if (last && last.step.kind === "tool" && !last.result) last.result = s
      else if (s.detail.error) out.push({ step: { ...s, kind: "error" } })
      continue
    }
    out.push({ step: s })
  }
  return out
}

function code(raw: string): string {
  try { return JSON.parse(raw).code ?? raw } catch { return raw }
}
