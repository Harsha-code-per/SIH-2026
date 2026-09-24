import { useState } from "react"
import { AlertTriangle, Check, Copy, FileText, ListTree } from "lucide-react"
import { Steps, StepsContent, StepsItem, StepsTrigger } from "@/components/prompt-kit/steps"
import { TextShimmer } from "@/components/prompt-kit/text-shimmer"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { currentActivity, describe, summarise } from "@/lib/steps"
import type { Step, Turn } from "@/lib/types"
import type { LiveTurn } from "@/hooks/use-thread"
import { cn } from "@/lib/utils"
import { AnswerBody, RouteChip, Seal } from "./answer"
import { FileCard } from "./inspector"

export function UserBubble({ text, attachment }: { text: string; attachment?: string | null }) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      {attachment && (
        <div className="flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1 text-xs text-muted-foreground">
          <FileText className="size-3.5 text-brand" />
          {attachment.split("/").pop()}
        </div>
      )}
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md
                      bg-secondary px-4 py-2.5 text-[15px] leading-relaxed">
        {text}
      </div>
    </div>
  )
}

/** Claude's pattern: one quiet line that says what was done, expanding into
 *  the steps. The Inspector holds the full detail. */
export function Activity({ steps, onOpen, live = false }: {
  steps: Step[]
  onOpen?: () => void
  live?: boolean
}) {
  const visible = steps.filter((s) => s.kind === "tool" || s.kind === "route"
    || s.kind === "verify" || s.kind === "escalate" || s.kind === "retry" || s.kind === "error")
  if (!visible.length && !live) return null
  return (
    <Steps defaultOpen={false} className="mb-2">
      <StepsTrigger leftIcon={<ListTree className="size-4" />}
                    className="text-[13px] text-muted-foreground hover:text-foreground">
        {live ? <TextShimmer>{currentActivity(steps)}</TextShimmer> : summarise(steps)}
      </StepsTrigger>
      <StepsContent>
        <div className="space-y-1.5">
          {visible.map((s) => {
            const { verb, arg } = describe(s)
            return (
              <StepsItem key={`${s.n}-${s.kind}`}
                         className={cn("text-[13px]",
                           s.kind === "error" && "text-bad",
                           s.kind === "verify" && s.label === "checks passed" && "text-ok")}>
                <span className="text-foreground/90">{verb}</span>
                {arg && <span className="text-muted-foreground"> · {arg}</span>}
              </StepsItem>
            )
          })}
          {onOpen && (
            <button onClick={onOpen}
                    className="text-xs font-medium text-brand hover:underline">
              Open in Inspector
            </button>
          )}
        </div>
      </StepsContent>
    </Steps>
  )
}

export function AssistantTurn({ turn, onInspect, onCite }: {
  turn: Turn
  onInspect: () => void
  onCite?: (id: string) => void
}) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="group/turn">
      <Activity steps={turn.steps} onOpen={onInspect} />
      {turn.answer ? (
        <AnswerBody text={turn.answer} evidence={turn.evidence} onCite={onCite} />
      ) : !turn.deliverables.length && (
        <p className="text-sm text-muted-foreground">No answer was produced.</p>
      )}
      {turn.deliverables.length > 0 && (
        <div className="mt-4 space-y-2">
          {turn.deliverables.map((f) => <FileCard key={f.path} file={f} compact />)}
        </div>
      )}
      <Seal turn={turn} />
      <div className="mt-2 flex items-center gap-1">
        <RouteChip decision={turn.decision} />
        <div className="flex items-center gap-0.5 opacity-0 transition-opacity
                        group-hover/turn:opacity-100 focus-within:opacity-100">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="size-7 text-muted-foreground"
                    aria-label="Copy answer"
                    onClick={async () => {
                      await navigator.clipboard.writeText(turn.answer)
                      setCopied(true); setTimeout(() => setCopied(false), 1500)
                    }}>
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{copied ? "Copied" : "Copy"}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="size-7 text-muted-foreground"
                    aria-label="Inspect this answer" onClick={onInspect}>
              <ListTree className="size-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Inspect</TooltipContent>
        </Tooltip>
        </div>
      </div>
    </div>
  )
}

export function LiveAssistant({ live }: { live: LiveTurn }) {
  if (live.status === "error") {
    return (
      <div className="space-y-2">
        <Activity steps={live.steps} />
        <div className="flex items-start gap-2 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-[13px]">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-bad" />
          <span>{live.error}</span>
        </div>
      </div>
    )
  }
  return <Activity steps={live.steps} live />
}
