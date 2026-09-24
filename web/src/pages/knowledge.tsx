import { useState } from "react"
import { BookOpen, FileText, Loader2, RefreshCw, Search } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PassageText, citeParts } from "@/components/app/answer"
import { Page, PageState } from "@/components/app/page"
import { useAuth } from "@/hooks/use-auth"
import { useLoad } from "@/hooks/use-load"
import { api } from "@/lib/api"
import type { Passage } from "@/lib/types"

interface Documents { chunks: number; documents: { name: string; chunks: number }[] }

export function KnowledgePage() {
  const { can } = useAuth()
  const docs = useLoad<Documents>("/api/kb/documents")
  const [rebuilding, setRebuilding] = useState(false)
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<{ query: string; passages: Passage[] } | null>(null)
  const [searching, setSearching] = useState(false)

  const rebuild = async () => {
    setRebuilding(true)
    try {
      const s = await api.post<{ documents?: number; chunks?: number }>("/api/kb/build")
      toast.success(`Index rebuilt: ${s.documents ?? "?"} documents, ${s.chunks ?? "?"} passages.`)
      docs.reload()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Rebuild failed")
    } finally {
      setRebuilding(false)
    }
  }

  const search = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    setSearching(true)
    try {
      setResults(await api.get(`/api/kb/search?q=${encodeURIComponent(q)}&k=8`))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Search failed")
    } finally {
      setSearching(false)
    }
  }

  const max = Math.max(1, ...(docs.data?.documents.map((d) => d.chunks) ?? [1]))

  return (
    <Page title="Knowledge base"
          description="The documents every answer is checked against. Nothing here leaves this machine."
          actions={can("manage_kb") && (
            <Button variant="outline" size="sm" onClick={rebuild} disabled={rebuilding}>
              {rebuilding ? <Loader2 className="animate-spin" /> : <RefreshCw />} Rebuild index
            </Button>
          )}>

      <form onSubmit={search} className="relative mb-8">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder="Search the way the assistant does — try “vibration limit zone D”"
               aria-label="Search the knowledge base" className="h-11 pl-9 pr-24 text-[15px]" />
        <Button type="submit" size="sm" disabled={searching || !query.trim()}
                className="absolute right-1.5 top-1/2 -translate-y-1/2">
          {searching ? <Loader2 className="animate-spin" /> : "Search"}
        </Button>
      </form>

      {results && (
        <section className="mb-10">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            {results.passages.length} passages for “{results.query}”
          </h2>
          <div className="space-y-3">
            {results.passages.map((p, i) => {
              const { doc, section } = citeParts(p, p.id)
              return (
                <article key={p.id} className="rounded-xl border bg-card p-4">
                  <header className="mb-2 flex items-center gap-2 text-xs">
                    <span className="tabular w-4 text-muted-foreground">{i + 1}</span>
                    <BookOpen className="size-3.5 text-brand" />
                    <span className="font-medium">{section ? `${section} · ${doc}` : doc}</span>
                    <span className="ml-auto font-mono text-muted-foreground">
                      {p.id.split("#")[1] && `#${p.id.split("#")[1]}`} · {p.score.toFixed(2)}
                    </span>
                  </header>
                  <PassageText text={p.text} className="text-sm" />
                </article>
              )
            })}
            {!results.passages.length && (
              <p className="text-sm text-muted-foreground">Nothing matched. The assistant would say so rather than guess.</p>
            )}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-3 flex items-baseline justify-between text-sm font-medium text-muted-foreground">
          Documents
          {docs.data && (
            <span className="tabular font-normal">
              {docs.data.documents.length} documents · {docs.data.chunks} passages indexed
            </span>
          )}
        </h2>
        <PageState loading={docs.loading && !docs.data} error={docs.error} />
        {docs.data && (
          <ul className="divide-y rounded-xl border bg-card">
            {docs.data.documents.map((d) => (
              <li key={d.name} className="flex items-center gap-3 px-4 py-3">
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate text-sm font-medium">{d.name}</span>
                <div className="hidden h-1.5 w-32 overflow-hidden rounded-full bg-muted sm:block" aria-hidden>
                  <div className="h-full rounded-full bg-brand/60" style={{ width: `${(d.chunks / max) * 100}%` }} />
                </div>
                <span className="tabular w-20 text-right text-xs text-muted-foreground">
                  {d.chunks} passage{d.chunks === 1 ? "" : "s"}
                </span>
              </li>
            ))}
            {!docs.data.documents.length && (
              <li className="px-4 py-8 text-center text-sm text-muted-foreground">
                No documents indexed. Add files to <code>data/kb/</code> and rebuild — see docs/playbooks/add-knowledge.md.
              </li>
            )}
          </ul>
        )}
      </section>
    </Page>
  )
}
