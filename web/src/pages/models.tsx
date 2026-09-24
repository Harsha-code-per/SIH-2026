import { useState } from "react"
import { ArrowRight, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Page, PageState } from "@/components/app/page"
import { useAuth } from "@/hooks/use-auth"
import { useLoad } from "@/hooks/use-load"
import { api } from "@/lib/api"
import { TIER } from "@/lib/tiers"
import type { Status, Tier } from "@/lib/types"
import { cn } from "@/lib/utils"

/** `{task: analyze}` → "task is analyze"; `{input_tokens_gt: 4000}` → "input over 4000 tokens". */
function condition(c: Record<string, unknown>): string {
  const parts = Object.entries(c).map(([k, v]) => {
    if (k === "input_tokens_gt") return `input over ${v} tokens`
    if (v === true) return k.replace(/^has_/, "has ").replace(/_/g, " ")
    return `${k.replace(/_/g, " ")} is ${v}`
  })
  return parts.length ? parts.join(" and ") : "anything else"
}

function TierChip({ tier, className }: { tier: Tier; className?: string }) {
  return (
    <span className={cn(className, "inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-1.5 font-mono text-[11px] font-semibold",
                        TIER[tier].tone)}>
      {tier} <span className="font-sans font-medium">{TIER[tier].name}</span>
    </span>
  )
}

export function ModelsPage() {
  const { can } = useAuth()
  const { data, error, loading, reload } = useLoad<Status>("/api/status")
  const [reloading, setReloading] = useState(false)

  const reloadRegistry = async () => {
    setReloading(true)
    try {
      const r = await api.post<{ added: string[]; removed: string[] }>("/api/registry/reload")
      const change = [
        r.added.length && `added ${r.added.join(", ")}`,
        r.removed.length && `removed ${r.removed.join(", ")}`,
      ].filter(Boolean).join("; ")
      toast.success(change ? `Registry reloaded: ${change}.` : "Registry reloaded. No models changed.")
      reload()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reload failed")
    } finally {
      setReloading(false)
    }
  }

  return (
    <Page title="Models"
          description={<>Every request is routed by rule, not by a model. Adding a model is an edit to <code>models.yaml</code>.</>}
          actions={can("manage_models") && (
            <Button variant="outline" size="sm" onClick={reloadRegistry} disabled={reloading}>
              {reloading ? <Loader2 className="animate-spin" /> : <RefreshCw />} Reload registry
            </Button>
          )}>
      <PageState loading={loading && !data} error={error} />
      {data && (
        <>
          <div className="mb-8 flex flex-wrap gap-x-8 gap-y-2 rounded-xl border bg-card px-4 py-3 text-sm">
            <div><span className="text-muted-foreground">Mode</span> <span className="ml-1.5 font-medium capitalize">{data.mode}</span></div>
            <div className="min-w-0"><span className="text-muted-foreground">Endpoint</span> <span className="ml-1.5 break-all font-mono text-xs">{data.endpoint}</span></div>
          </div>

          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Tiers</h2>
          <ul className="divide-y rounded-xl border bg-card">
            <li className="flex flex-wrap items-start gap-3 px-4 py-3.5">
              <TierChip tier="L0" className="w-36" />
              <div className="min-w-0 flex-1">
                <div className="font-mono text-xs">calculate · percent_change</div>
                <p className="mt-1 text-sm text-muted-foreground">Exact arithmetic in code. No model is called, so no number is generated.</p>
              </div>
            </li>
            {data.models.map((m) => (
              <li key={m.id} className="flex flex-wrap items-start gap-3 px-4 py-3.5">
                <TierChip tier={m.tier} className="w-36" />
                <div className="min-w-0 flex-1">
                  <div className="break-all font-mono text-xs">{m.name}</div>
                  {Object.entries(m.modes).filter(([mode, name]) => mode !== data.mode && name).map(([mode, name]) => (
                    <div key={mode} className="mt-0.5 break-all font-mono text-xs text-muted-foreground">
                      <span className="font-sans">{mode === "sovereign" ? "On-premise" : mode}:</span> {name}
                    </div>
                  ))}
                  <p className="mt-1 text-sm text-muted-foreground">{m.why}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {m.caps.map((c) => (
                      <span key={c} className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">{c}</span>
                    ))}
                    {m.max_tokens && (
                      <span className="tabular rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                        {m.max_tokens.toLocaleString()} output tokens
                      </span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <h2 className="mb-1 mt-10 text-sm font-medium text-muted-foreground">Routing rules</h2>
          <p className="mb-3 text-xs text-muted-foreground">Checked top to bottom; the first match wins.</p>
          <ol className="divide-y rounded-xl border bg-card">
            {data.rules.map((r, i) => (
              <li key={r.name} className="grid grid-cols-[1.5rem_1fr] gap-x-2 px-4 py-3 sm:grid-cols-[1.5rem_1fr_auto] sm:items-center">
                <span className="tabular text-xs text-muted-foreground">{i + 1}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5 text-sm">
                    <span className="font-medium">{r.name}</span>
                    <span className="text-muted-foreground">· {condition(r.if)}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{r.why}</p>
                </div>
                {r.then.tier && (
                  <div className="col-start-2 mt-2 flex items-center gap-1.5 sm:col-start-3 sm:mt-0">
                    <ArrowRight className="size-3.5 text-muted-foreground" />
                    <TierChip tier={r.then.tier} />
                  </div>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
    </Page>
  )
}
