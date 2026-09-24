import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react"
import { useContainment } from "@/hooks/use-containment"
import { cn } from "@/lib/utils"
import type { Egress } from "@/lib/types"

type Level = "contained" | "leaked" | "unenforced" | "unverified" | "connecting"

export function level(e: Egress | null): Level {
  if (!e) return "connecting"
  if (e.contained) return "contained"
  if (e.leaked_count) return "leaked"
  if (!e.enforced) return "unenforced"
  return "unverified"
}

const LABEL: Record<Level, string> = {
  contained: "Contained",
  leaked: "Leaked",
  unenforced: "Not enforced",
  unverified: "Unverified",
  connecting: "Checking…",
}

const TONE: Record<Level, string> = {
  contained: "text-ok",
  leaked: "text-bad",
  unenforced: "text-warn",
  unverified: "text-warn",
  connecting: "text-muted-foreground",
}

/** The sovereignty indicator. Always on screen, green only when the backend
 *  says so -- a cloud assistant cannot have one of these. */
export function ContainmentBadge({ compact = false, className }: {
  compact?: boolean
  className?: string
}) {
  const e = useContainment()
  const l = level(e)
  const Icon = l === "contained" ? ShieldCheck : l === "leaked" ? ShieldAlert : ShieldQuestion
  const detail = l === "contained"
    ? `${e!.enforcement}. ${e!.leaked_count} leaked.`
    : l === "leaked" ? `${e!.leaked_count} connection(s) left without permission.`
    : l === "unenforced" ? "Nothing is stopping outbound traffic here — run the stack with make up."
    : l === "unverified" ? "Enforcement detected, but no observer is running."
    : "Connecting to the containment monitor."

  return (
    <div className={cn("flex items-center gap-2 min-w-0", className)}
         title={detail} role="status" aria-live="polite">
      <span className={cn("relative flex size-4 shrink-0 items-center justify-center", TONE[l])}>
        <Icon className="size-4" />
        {l === "contained" && (
          <span className="absolute -right-0.5 -top-0.5 size-1.5 rounded-full bg-ok
                           animate-pulse motion-reduce:animate-none" />
        )}
      </span>
      {!compact && (
        <span className="min-w-0 truncate text-xs">
          <span className={cn("font-medium", TONE[l])}>{LABEL[l]}</span>
          {e && l === "contained" && (
            <span className="text-muted-foreground"> · nothing leaves</span>
          )}
        </span>
      )}
    </div>
  )
}
