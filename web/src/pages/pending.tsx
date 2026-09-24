import { SidebarTrigger } from "@/components/ui/sidebar"

// Replaced in phase E of the redesign (docs/ROADMAP.md). Kept honest in the
// meantime: it says what the page is and that it is not built yet, rather
// than rendering controls that do nothing.
export function PendingPage({ title }: { title: string }) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-12 items-center gap-2 px-3">
        <SidebarTrigger className="text-muted-foreground md:hidden" />
        <h1 className="text-sm font-medium">{title}</h1>
      </header>
      <div className="grid flex-1 place-items-center p-6 text-center">
        <div>
          <p className="font-medium">{title}</p>
          <p className="mt-1 text-sm text-muted-foreground">This view is being rebuilt for the new interface.</p>
        </div>
      </div>
    </div>
  )
}
