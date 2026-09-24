import { useEffect, useState } from "react"
import {
  AlertTriangle, ArrowRightLeft, BookOpen, Calculator, CheckCircle2, Code2, Download,
  FileSpreadsheet, FileText, Loader2, PanelRightClose, RefreshCw, Route, ScanLine,
  Search, ShieldCheck, Zap,
} from "lucide-react"
import { toast } from "sonner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ContainmentBadge, level } from "./containment"
import { PassageText } from "./answer"
import { useContainment } from "@/hooks/use-containment"
import { api } from "@/lib/api"
import { describe } from "@/lib/steps"
import { TIER } from "@/lib/tiers"
import type { Decision, Deliverable, Passage, Step } from "@/lib/types"
import { cn } from "@/lib/utils"

export type InspectorTab = "activity" | "sources" | "files" | "shield"

export interface InspectorSubject {
  steps: Step[]
  decision?: Decision | Record<string, never> | null
  evidence: Passage[]
  deliverables: Deliverable[]
  live: boolean
}

export function Inspector({ subject, tab, setTab, onClose, highlight }: {
  subject: InspectorSubject | null
  tab: InspectorTab
  setTab: (t: InspectorTab) => void
  onClose: () => void
  /** a passage id to scroll to and mark, when a citation pill was clicked */
  highlight?: string | null
}) {
  return (
    <aside aria-label="Inspector"
           className="flex h-full w-full flex-col border-l bg-sidebar">
      <Tabs value={tab} onValueChange={(v) => setTab(v as InspectorTab)}
            className="flex h-full min-h-0 flex-col gap-0">
        <div className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
          <TabsList className="h-8 bg-transparent p-0">
            {(["activity", "sources", "files", "shield"] as InspectorTab[]).map((t) => (
              <TabsTrigger key={t} value={t}
                className="h-8 rounded-md px-2.5 text-[13px] capitalize data-[state=active]:bg-sidebar-accent data-[state=active]:shadow-none">
                {t}
                {t === "sources" && subject?.evidence.length ? (
                  <span className="tabular ml-1 text-xs text-muted-foreground">{subject.evidence.length}</span>
                ) : null}
                {t === "files" && subject?.deliverables.length ? (
                  <span className="tabular ml-1 text-xs text-muted-foreground">{subject.deliverables.length}</span>
                ) : null}
              </TabsTrigger>
            ))}
          </TabsList>
          <Button variant="ghost" size="icon" className="ml-auto size-8 text-muted-foreground"
                  onClick={onClose} aria-label="Close Inspector">
            <PanelRightClose className="size-4" />
          </Button>
        </div>

        {/* Radix wraps the viewport content in display:table, which grows to
            fit the widest unbreakable line -- a markdown table row in a
            passage pushed every card off the panel's edge. Forced to block. */}
        <ScrollArea className="min-h-0 flex-1 [&_[data-radix-scroll-area-viewport]>div]:!block">
          <div className="p-4">
            <TabsContent value="activity" className="mt-0">
              {subject ? <ActivityTab subject={subject} /> : <Empty text="Run a task to see each step it takes." />}
            </TabsContent>
            <TabsContent value="sources" className="mt-0">
              {subject?.evidence.length ? <SourcesTab passages={subject.evidence} highlight={highlight} />
                : <Empty text="Passages retrieved from the knowledge base appear here, with how well each matched." />}
            </TabsContent>
            <TabsContent value="files" className="mt-0">
              {subject?.deliverables.length ? <FilesTab files={subject.deliverables} />
                : <Empty text="Documents and spreadsheets the agent writes appear here." />}
            </TabsContent>
            <TabsContent value="shield" className="mt-0">
              <ShieldTab />
            </TabsContent>
          </div>
        </ScrollArea>
      </Tabs>
    </aside>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="py-10 text-center text-sm text-muted-foreground">{text}</p>
}

const ICON: Record<string, typeof Search> = {
  kb_search: Search, read_document: BookOpen, parse_page: ScanLine,
  describe_image: ScanLine, calculate: Calculator, percent_change: Calculator,
  run_python: Code2, write_docx: FileText, write_xlsx: FileSpreadsheet,
}

function ActivityTab({ subject }: { subject: InspectorSubject }) {
  const d = subject.decision && "tier" in subject.decision ? subject.decision as Decision : null
  const route = d ?? (subject.steps.find((s) => s.kind === "route" && s.detail.tier)?.detail as unknown as Decision | undefined)
  const steps = subject.steps.filter((s) => s.kind !== "result" || s.detail.error)

  return (
    <div className="space-y-5">
      {route && (
        <section className="rounded-xl border bg-card p-3.5">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Route className="size-3.5" /> Routing
          </div>
          <div className="flex items-center gap-2">
            <span className={cn("rounded-md px-1.5 py-0.5 font-mono text-xs font-semibold",
                                TIER[route.tier]?.tone)}>{route.tier}</span>
            <span className="font-medium">{TIER[route.tier]?.name}</span>
          </div>
          <p className="mt-1.5 text-[13px] text-muted-foreground">{route.why}</p>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Model</dt>
            <dd className="truncate font-mono">{route.model_name ?? `tool: ${route.tool}`}</dd>
            <dt className="text-muted-foreground">Rule</dt><dd className="font-mono">{route.rule}</dd>
            <dt className="text-muted-foreground">Task</dt><dd>{route.features?.task}</dd>
            <dt className="text-muted-foreground">Escalates to</dt>
            <dd>{route.escalates_to ?? "— top tier"}</dd>
          </dl>
        </section>
      )}

      <section>
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Timeline
        </div>
        <ol className="relative space-y-0.5 before:absolute before:bottom-2 before:left-[11px] before:top-2 before:w-px before:bg-border">
          {steps.map((s) => {
            const { verb, arg } = describe(s)
            const Icon = s.kind === "tool" ? (ICON[s.label] ?? Zap)
              : s.kind === "verify" ? (s.label === "checks passed" ? CheckCircle2 : AlertTriangle)
              : s.kind === "escalate" || s.kind === "retry" ? RefreshCw
              : s.kind === "route" ? ArrowRightLeft
              : s.kind === "error" ? AlertTriangle : CheckCircle2
            const tone = s.kind === "error" ? "text-bad"
              : s.kind === "verify" ? (s.label === "checks passed" ? "text-ok" : "text-warn")
              : s.kind === "escalate" || s.kind === "retry" ? "text-warn" : "text-muted-foreground"
            return (
              <li key={`${s.n}-${s.kind}`} className="relative flex gap-3 py-1.5">
                <span className={cn("relative z-10 grid size-6 shrink-0 place-items-center rounded-full border bg-sidebar", tone)}>
                  <Icon className="size-3.5" />
                </span>
                <div className="min-w-0 pt-0.5 text-[13px]">
                  <div className="font-medium">{verb}</div>
                  {arg && <div className="break-words text-muted-foreground">{arg}</div>}
                  {s.label === "run_python" && typeof s.detail.arguments === "string" && (
                    <pre className="mt-1.5 max-h-40 overflow-auto rounded-md bg-muted p-2 font-mono text-[11px]">
                      {safeCode(s.detail.arguments)}
                    </pre>
                  )}
                  {typeof s.detail.stdout === "string" && s.detail.stdout.trim() && (
                    <pre className="mt-1.5 max-h-40 overflow-auto rounded-md bg-muted p-2 font-mono text-[11px]">
                      {s.detail.stdout}
                    </pre>
                  )}
                </div>
              </li>
            )
          })}
          {subject.live && (
            <li className="relative flex gap-3 py-1.5">
              <span className="relative z-10 grid size-6 shrink-0 place-items-center rounded-full border bg-sidebar text-brand">
                <Loader2 className="size-3.5 animate-spin" />
              </span>
              <span className="pt-0.5 text-[13px] text-muted-foreground">Working…</span>
            </li>
          )}
        </ol>
      </section>
    </div>
  )
}

function safeCode(raw: string): string {
  try { return JSON.parse(raw).code ?? raw } catch { return raw }
}

function SourcesTab({ passages, highlight }: { passages: Passage[]; highlight?: string | null }) {
  useEffect(() => {
    if (!highlight) return
    const el = document.getElementById(`source-${highlight}`)
    el?.scrollIntoView({ block: "center", behavior: "smooth" })
    el?.focus({ preventScroll: true })
  }, [highlight])
  const byDoc = new Map<string, Passage[]>()
  for (const p of [...passages].sort((a, b) => b.score - a.score)) {
    const doc = p.id.split("#")[0]
    byDoc.set(doc, [...(byDoc.get(doc) ?? []), p])
  }
  return (
    <div className="space-y-5">
      {[...byDoc.entries()].map(([doc, items]) => (
        <section key={doc}>
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <BookOpen className="size-3.5" />
            <span className="truncate">{doc}</span>
            <span className="tabular ml-auto">{items.length}</span>
          </div>
          <div className="space-y-2">
            {items.map((p) => (
              <article key={p.id} id={`source-${p.id}`} tabIndex={-1}
                       className={cn("rounded-xl border bg-card p-3 outline-none transition-shadow",
                                     p.id === highlight && "border-brand/60 ring-2 ring-brand/25")}>
                <div className="mb-1 flex items-baseline gap-2">
                  <span className="font-mono text-xs font-semibold text-brand">#{p.id.split("#")[1]}</span>
                  <span className="min-w-0 truncate text-xs text-muted-foreground">{p.cite.split(" · ").slice(1).join(" · ")}</span>
                  <span className="tabular ml-auto text-xs text-muted-foreground" title="Hybrid retrieval score">
                    {p.score.toFixed(2)}
                  </span>
                </div>
                <PassageText text={p.text}
                             className={p.id === highlight ? "" : "line-clamp-5"} />
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

interface Outline {
  name: string; bytes: number; kind: string; title?: string
  headings?: string[]; tables?: number; citations?: string[]
  sheets?: { name: string; rows: number; columns: number }[]
}

function FilesTab({ files }: { files: Deliverable[] }) {
  return <div className="space-y-3">{files.map((f) => <FileCard key={f.path} file={f} />)}</div>
}

export function FileCard({ file, compact = false }: { file: Deliverable; compact?: boolean }) {
  const name = file.path.split("/").pop()!
  const [outline, setOutline] = useState<Outline | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    api.get<Outline>(`/api/files/${encodeURIComponent(name)}/outline`).then(setOutline).catch(() => {})
  }, [name])
  const Icon = name.endsWith(".xlsx") ? FileSpreadsheet : FileText
  const meta = outline?.kind === "docx"
    ? [outline.headings?.length ? `${outline.headings.length} sections` : null,
       outline.tables ? `${outline.tables} table${outline.tables > 1 ? "s" : ""}` : null,
       outline.citations?.length ? `${outline.citations.length} citations` : null]
        .filter(Boolean).join(" · ")
    : outline?.sheets ? outline.sheets.map((s) => `${s.rows} rows`).join(" · ") : ""

  return (
    <div className="flex items-center gap-3 rounded-xl border bg-card p-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
        <Icon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium">{outline?.title && !compact ? outline.title : name}</div>
        <div className="truncate text-xs text-muted-foreground">
          {name.endsWith(".xlsx") ? "Spreadsheet" : "Word document"}
          {meta && ` · ${meta}`} · {(file.bytes / 1024).toFixed(0)} KB
        </div>
      </div>
      <Button size="sm" variant="secondary" disabled={busy}
              onClick={async () => {
                setBusy(true)
                try { await api.download(file.download, name) }
                catch (e) { toast.error(e instanceof Error ? e.message : "Download failed") }
                finally { setBusy(false) }
              }}>
        {busy ? <Loader2 className="animate-spin" /> : <Download />} Download
      </Button>
    </div>
  )
}

function ShieldTab() {
  const e = useContainment()
  const [trip, setTrip] = useState<{ blocked: boolean; error: string | null; elapsed_ms: number; target: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const l = level(e)

  return (
    <div className="space-y-5">
      <section className="rounded-xl border bg-card p-3.5">
        <ContainmentBadge />
        {e && (
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
            <dt className="text-muted-foreground">Enforcement</dt>
            <dd className={e.enforced ? "text-ok" : "text-warn"}>
              {e.enforcement.split(" -- ")[0]}
            </dd>
            <dt className="text-muted-foreground">Observer</dt><dd>{e.status}</dd>
            <dt className="text-muted-foreground">Permitted</dt>
            <dd className="font-mono">{e.allowlist.join(", ")}</dd>
          </dl>
        )}
      </section>

      <div className="grid grid-cols-3 gap-2">
        {[["Allowed", e?.allowed_count, "text-warn"], ["Blocked", e?.blocked_count, "text-ok"],
          ["Leaked", e?.leaked_count, e?.leaked_count ? "text-bad" : "text-muted-foreground"]].map(([k, v, tone]) => (
          <div key={k as string} className="rounded-xl border bg-card p-2.5 text-center">
            <div className={cn("tabular text-lg font-semibold", tone as string)}>{(v as number) ?? "–"}</div>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{k as string}</div>
          </div>
        ))}
      </div>

      <section className="space-y-2">
        <Button variant="outline" className="w-full border-bad/40 text-bad hover:bg-bad/10 hover:text-bad"
                disabled={busy}
                onClick={async () => {
                  setBusy(true)
                  try { setTrip(await api.post("/api/tripwire")) }
                  catch (err) { toast.error(err instanceof Error ? err.message : "Tripwire failed") }
                  finally { setBusy(false) }
                }}>
          {busy ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
          Attempt an external call
        </Button>
        <p className="text-xs text-muted-foreground">
          Genuinely tries to reach {trip?.target ?? "api.openai.com"}. It must fail.
        </p>
        {trip && (
          <div className={cn("rounded-xl border p-3 text-[13px]",
                             trip.blocked ? "border-ok/30 bg-ok/10" : "border-bad/30 bg-bad/10")}>
            <div className={cn("font-semibold", trip.blocked ? "text-ok" : "text-bad")}>
              {trip.blocked ? "Blocked" : "Not contained"} · {trip.elapsed_ms} ms
            </div>
            {trip.error && <div className="mt-1 font-mono text-xs text-muted-foreground">{trip.error}</div>}
          </div>
        )}
      </section>

      {e && e.events.length > 0 && (
        <section>
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Outbound attempts
          </div>
          <ul className="divide-y rounded-xl border bg-card">
            {[...e.events].reverse().slice(0, 20).map((ev, i) => (
              <li key={i} className="flex items-center gap-2 px-3 py-2 font-mono text-xs">
                <span className={cn("w-16 shrink-0 font-semibold",
                  ev.verdict === "BLOCKED" ? "text-ok" : ev.verdict === "LEAKED" ? "text-bad" : "text-warn")}>
                  {ev.verdict}
                </span>
                <span className="tabular shrink-0 text-muted-foreground">
                  {new Date(ev.ts * 1000).toTimeString().slice(0, 8)}
                </span>
                <span className="min-w-0 truncate">{ev.dst}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {l === "unenforced" && (
        <p className="text-xs text-warn">
          Running outside the contained stack. Start it with <span className="font-mono">make up</span>.
        </p>
      )}
    </div>
  )
}
