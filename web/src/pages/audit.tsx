import { useMemo, useState } from "react"
import { RefreshCw, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Page, PageState } from "@/components/app/page"
import { useLoad } from "@/hooks/use-load"
import { cn } from "@/lib/utils"

interface Entry { ts: number; kind: string; [field: string]: unknown }

// Agent steps are most of the log; they are there for forensics, not reading.
const FILTERS: { id: string; label: string; match: (k: string) => boolean }[] = [
  { id: "activity", label: "Activity", match: (k) => !k.startsWith("step.") },
  { id: "tasks", label: "Tasks", match: (k) => k.startsWith("task.") || k === "upload" },
  { id: "access", label: "Access", match: (k) => k.startsWith("login") || k.startsWith("user.") || k.startsWith("password") },
  { id: "security", label: "Containment", match: (k) => k === "tripwire" },
  { id: "steps", label: "Agent steps", match: (k) => k.startsWith("step.") },
]

const TONE: Record<string, string> = {
  "login.failed": "text-bad", "task.failed": "text-bad", tripwire: "text-brand",
  "task.completed": "text-ok", "user.removed": "text-warn", "user.role_changed": "text-warn",
}

function summary(e: Entry): string {
  const { ts: _ts, kind: _k, user: _u, by: _b, ...rest } = e
  if (e.kind === "task.received") return String(rest.prompt ?? "")
  if (e.kind === "task.completed") return `verdict ${rest.verdict} · ${rest.model ?? "no model"}`
  if (e.kind === "tripwire") return `${rest.target} ${rest.blocked ? "blocked" : "REACHED"} in ${rest.elapsed_ms} ms · ${rest.detail ?? ""}`
  return Object.entries(rest)
    .filter(([, v]) => v !== "" && v != null && !(typeof v === "object" && !Object.keys(v as object).length))
    .map(([k, v]) => `${k} ${typeof v === "object" ? JSON.stringify(v) : v}`)
    .join(" · ")
}

export function AuditPage() {
  const { data, error, loading, reload } = useLoad<{ entries: Entry[] }>("/api/audit?n=2000")
  const [filter, setFilter] = useState("activity")
  const [query, setQuery] = useState("")

  const rows = useMemo(() => {
    const f = FILTERS.find((x) => x.id === filter)!
    const q = query.trim().toLowerCase()
    return (data?.entries ?? [])
      .filter((e) => f.match(e.kind))
      .filter((e) => !q || JSON.stringify(e).toLowerCase().includes(q))
      .reverse()
      .slice(0, 300)
  }, [data, filter, query])

  return (
    <Page title="Audit log"
          description="Append-only record of every sign-in, task, tool call and change. Newest first."
          actions={
            <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
              <RefreshCw className={cn(loading && "animate-spin")} /> Refresh
            </Button>
          }>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div role="tablist" aria-label="Filter events" className="flex flex-wrap gap-1 rounded-lg bg-muted p-1">
          {FILTERS.map((f) => (
            <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}
                    className={cn("rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                      filter === f.id ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative ml-auto w-full sm:w-64">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter"
                 aria-label="Filter events" className="h-8 pl-8 text-[13px]" />
        </div>
      </div>

      <PageState loading={loading && !data} error={error} />
      {data && (
        <div className="overflow-hidden rounded-xl border bg-card">
          <table className="w-full table-fixed text-[13px]">
            <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
              <tr>
                <th className="w-28 px-3 py-2 font-medium sm:w-36">Time</th>
                <th className="w-32 px-3 py-2 font-medium sm:w-40">Event</th>
                <th className="hidden w-24 px-3 py-2 font-medium sm:table-cell">User</th>
                <th className="px-3 py-2 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((e, i) => {
                const d = new Date(e.ts * 1000)
                return (
                  <tr key={`${e.ts}-${i}`} className="align-top hover:bg-muted/30">
                    <td className="tabular px-3 py-2 text-muted-foreground" title={d.toISOString()}>
                      <span className="hidden sm:inline">{d.toLocaleDateString(undefined, { day: "numeric", month: "short" })} </span>
                      {d.toLocaleTimeString(undefined, { hour12: false })}
                    </td>
                    <td className={cn("truncate px-3 py-2 font-mono text-xs", TONE[e.kind])}>{e.kind}</td>
                    <td className="hidden truncate px-3 py-2 sm:table-cell">{String(e.user ?? e.by ?? e.username ?? "")}</td>
                    <td className="truncate px-3 py-2 text-muted-foreground" title={summary(e)}>{summary(e)}</td>
                  </tr>
                )
              })}
              {!rows.length && (
                <tr><td colSpan={4} className="px-3 py-10 text-center text-muted-foreground">No events match.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {rows.length === 300 && (
        <p className="mt-3 text-center text-xs text-muted-foreground">Showing the latest 300. The full log is <code>data/audit.jsonl</code>.</p>
      )}
    </Page>
  )
}
