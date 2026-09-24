import { useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import {
  BookOpen, Check, ChevronsUpDown, Cpu, LogOut, Monitor, Moon, MoreHorizontal,
  Pencil, ScrollText, Search, Settings, SquarePen, Sun, Trash2, Users,
} from "lucide-react"
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent,
  SidebarGroupLabel, SidebarHeader, SidebarMenu, SidebarMenuAction,
  SidebarMenuButton, SidebarMenuItem, SidebarMenuSkeleton, SidebarRail,
  SidebarTrigger, useSidebar,
} from "@/components/ui/sidebar"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubContent,
  DropdownMenuSubTrigger, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Brand } from "./brand"
import { ContainmentBadge } from "./containment"
import { useAuth } from "@/hooks/use-auth"
import { groupByAge, useConversations } from "@/hooks/use-conversations"
import { type Theme, useTheme } from "@/hooks/use-theme"
import type { ConversationSummary } from "@/lib/types"

export function AppSidebar({ onOpenSettings }: { onOpenSettings: () => void }) {
  const { user, can, signOut } = useAuth()
  const { list, loading, rename, remove } = useConversations()
  const { theme, setTheme } = useTheme()
  const { id: activeId } = useParams()
  const navigate = useNavigate()
  const { state, setOpenMobile } = useSidebar()
  const [query, setQuery] = useState("")
  const [renaming, setRenaming] = useState<ConversationSummary | null>(null)
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null)

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    return groupByAge(q ? list.filter((c) => c.title.toLowerCase().includes(q)) : list)
  }, [list, query])

  const go = (to: string) => { navigate(to); setOpenMobile(false) }
  const initials = (user?.display || user?.username || "?")
    .split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="gap-1 pb-0">
        <div className="flex h-9 items-center justify-between px-1.5
                        group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <Brand className="group-data-[collapsible=icon]:hidden" />
          <SidebarTrigger className="text-muted-foreground" />
        </div>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="New conversation" onClick={() => go("/")}
                               className="font-medium">
              <SquarePen /> <span>New conversation</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Knowledge base" onClick={() => go("/knowledge")}>
              <BookOpen /> <span>Knowledge base</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {can("manage_users") && (
          <SidebarGroup>
            <SidebarGroupLabel>Administration</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton tooltip="Users" onClick={() => go("/admin/users")}>
                    <Users /> <span>Users</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton tooltip="Models" onClick={() => go("/admin/models")}>
                    <Cpu /> <span>Models</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                {can("read_audit") && (
                  <SidebarMenuItem>
                    <SidebarMenuButton tooltip="Audit log" onClick={() => go("/admin/audit")}>
                      <ScrollText /> <span>Audit log</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {state === "expanded" && (
          <div className="px-3 pt-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5
                                 -translate-y-1/2 text-muted-foreground" />
              <Input value={query} onChange={(e) => setQuery(e.target.value)}
                     placeholder="Search conversations" aria-label="Search conversations"
                     className="h-8 border-transparent bg-sidebar-accent/60 pl-8 text-[13px]
                                shadow-none focus-visible:border-sidebar-border" />
            </div>
          </div>
        )}

        {loading && !list.length && (
          <SidebarGroup className="group-data-[collapsible=icon]:hidden">
            <SidebarMenu>
              {Array.from({ length: 5 }).map((_, i) => (
                <SidebarMenuItem key={i}><SidebarMenuSkeleton /></SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        )}

        {!loading && !list.length && state === "expanded" && (
          <p className="px-4 py-6 text-center text-xs text-muted-foreground">
            Your conversations will appear here.
          </p>
        )}

        {query && !groups.length && list.length > 0 && (
          <p className="px-4 py-6 text-center text-xs text-muted-foreground">
            No conversation matches “{query}”.
          </p>
        )}

        {groups.map(([label, items]) => (
          <SidebarGroup key={label} className="group-data-[collapsible=icon]:hidden">
            <SidebarGroupLabel>{label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {items.map((c) => (
                  <SidebarMenuItem key={c.id}>
                    <SidebarMenuButton asChild isActive={c.id === activeId}
                                       className="text-[13px]">
                      <Link to={`/c/${c.id}`} onClick={() => setOpenMobile(false)}
                            title={c.title}>
                        <span className="truncate">{c.title}</span>
                      </Link>
                    </SidebarMenuButton>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <SidebarMenuAction showOnHover aria-label={`Options for ${c.title}`}>
                          <MoreHorizontal />
                        </SidebarMenuAction>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent side="right" align="start" className="w-40">
                        <DropdownMenuItem onSelect={() => setRenaming(c)}>
                          <Pencil /> Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(c)}>
                          <Trash2 /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="gap-1.5">
        <ContainmentBadge compact={state === "collapsed"}
                          className="px-2 py-1 group-data-[collapsible=icon]:justify-center" />
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
                  <Avatar className="size-8 rounded-lg">
                    <AvatarFallback className="rounded-lg bg-brand/15 text-xs font-semibold text-brand">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left leading-tight">
                    <span className="truncate text-[13px] font-medium">
                      {user?.display || user?.username}
                    </span>
                    <span className="truncate text-xs capitalize text-muted-foreground">
                      {user?.role}
                    </span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" className="w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="text-sm font-medium">{user?.display || user?.username}</div>
                  <div className="text-xs text-muted-foreground">{user?.username}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={onOpenSettings}>
                  <Settings /> Settings
                </DropdownMenuItem>
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    {theme === "dark" ? <Moon /> : theme === "light" ? <Sun /> : <Monitor />}
                    Theme
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    {(["light", "dark", "system"] as Theme[]).map((t) => (
                      <DropdownMenuItem key={t} onSelect={() => setTheme(t)} className="capitalize">
                        {t === "dark" ? <Moon /> : t === "light" ? <Sun /> : <Monitor />}
                        {t}
                        {theme === t && <Check className="ml-auto" />}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => signOut()}>
                  <LogOut /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />

      <RenameDialog conversation={renaming} onClose={() => setRenaming(null)}
                    onSave={async (title) => { if (renaming) await rename(renaming.id, title) }} />

      <AlertDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              “{deleting?.title}” will be removed. Documents it produced stay in the
              output folder, and the audit log keeps its record.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={async () => {
              if (!deleting) return
              await remove(deleting.id)
              if (deleting.id === activeId) navigate("/")
              setDeleting(null)
            }}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Sidebar>
  )
}

function RenameDialog({ conversation, onClose, onSave }: {
  conversation: ConversationSummary | null
  onClose: () => void
  onSave: (title: string) => Promise<void> | void
}) {
  const [title, setTitle] = useState("")
  return (
    <Dialog open={!!conversation}
            onOpenChange={(o) => { if (o && conversation) setTitle(conversation.title); if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md"
                     onOpenAutoFocus={() => conversation && setTitle(conversation.title)}>
        <DialogHeader><DialogTitle>Rename conversation</DialogTitle></DialogHeader>
        <form onSubmit={async (e) => {
          e.preventDefault()
          if (title.trim()) { await onSave(title.trim()); onClose() }
        }}>
          <Input value={title} onChange={(e) => setTitle(e.target.value)}
                 autoFocus maxLength={120} aria-label="Conversation title" />
          <DialogFooter className="mt-4">
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!title.trim()}>Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
