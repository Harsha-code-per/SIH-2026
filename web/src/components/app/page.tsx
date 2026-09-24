import { AlertTriangle, Loader2 } from "lucide-react"
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

/** A full-page view in the centre column -- knowledge, administration. The
 *  header matches the conversation page so moving between them does not jump. */
export function Page({ title, description, actions, children, className }: {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  const { open, isMobile } = useSidebar()
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-12 shrink-0 items-center gap-2 px-3">
        {(!open || isMobile) && <SidebarTrigger className="text-muted-foreground" />}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className={cn("mx-auto w-full max-w-4xl px-4 pb-16 pt-2 sm:px-8", className)}>
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
              {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
          {children}
        </div>
      </div>
    </div>
  )
}

/** Loading and failure, said the same way on every page. */
export function PageState({ loading, error }: { loading: boolean; error: string | null }) {
  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-bad" /> {error}
      </div>
    )
  }
  if (loading) {
    return (
      <div className="grid place-items-center py-16">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }
  return null
}

export function ago(ts: number | null | undefined): string {
  if (!ts) return "never"
  const s = Date.now() / 1000 - ts
  if (s < 60) return "just now"
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`
  return new Date(ts * 1000).toLocaleDateString()
}
