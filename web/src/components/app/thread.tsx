import { useState } from "react"
import { AlertTriangle, BookOpen, Check, Copy, FileText, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { Turn } from "@/lib/types"
import type { LiveTurn } from "@/hooks/use-thread"
import { AnswerBody, FAILURE, RouteChip, Seal } from "./answer"
import { FileCard, type InspectorTab } from "./inspector"
import { Reasoning } from "./reasoning"

export function UserBubble({ text, attachment }: { text: string; attachment?: string | null }) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      {attachment && (
        <div className="flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1 text-xs text-muted-foreground">
          <FileText className="size-3.5 text-brand" />
          {attachment.split("/").pop()}
        </div>
      )}
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md border border-brand/15
                      bg-gradient-to-br from-brand/14 to-brand-2/10 px-4 py-2.5 text-[15px] leading-relaxed">
        {text}
      </div>
    </div>
  )
}

export function AssistantTurn({ turn, onOpen, onCite }: {
  turn: Turn
  /** open the evidence panel on a tab, for this turn */
  onOpen: (tab: InspectorTab) => void
  onCite?: (id: string) => void
}) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="group/turn">
      <Reasoning steps={turn.steps} decision={turn.decision} thinking={turn.thinking} />
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
      <div className="mt-2 flex flex-wrap items-center gap-1">
        <RouteChip decision={turn.decision} />
        {turn.evidence.length > 0 && (
          // ChatGPT's pattern: the sources sit one click away, with a count.
          <button onClick={() => onOpen("sources")}
                  className="inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-[11px] font-medium
                             text-muted-foreground transition-colors hover:bg-brand/10 hover:text-brand">
            <BookOpen className="size-3" /> {turn.evidence.length} sources
          </button>
        )}
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
        </div>
      </div>
    </div>
  )
}

export function LiveAssistant({ live }: { live: LiveTurn }) {
  const running = live.status === "running"
  return (
    <div>
      <Reasoning steps={live.steps} thinking={live.thinking} live={running}
                 thinkingNow={live.thinkingNow} />
      {live.revision && running && (
        // The others quietly swap a bad answer for a better one. Here the
        // withdrawal is shown, because it is the proof the checks are real.
        <div className="mb-2 flex items-start gap-2 text-[13px] text-warn">
          <RefreshCw className="mt-0.5 size-3.5 shrink-0" />
          <span><span className="font-medium">Revising.</span> {FAILURE[live.revision] ?? live.revision}</span>
        </div>
      )}
      {live.text && (
        <div className={running ? "streaming" : undefined}>
          <AnswerBody text={live.text} evidence={[]} pending />
        </div>
      )}
      {live.status === "error" && (
        <div className="flex items-start gap-2 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-[13px]">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-bad" />
          <span>{live.error}</span>
        </div>
      )}
    </div>
  )
}
