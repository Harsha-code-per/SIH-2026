import { useEffect, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import {
  BookOpen, Cpu, MessageSquare, Monitor, Moon, ScrollText, Settings, SquarePen, Sun, Users,
} from "lucide-react"
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
  CommandSeparator, CommandShortcut,
} from "@/components/ui/command"
import { useAuth } from "@/hooks/use-auth"
import { useConversations } from "@/hooks/use-conversations"
import { useTheme } from "@/hooks/use-theme"
import { TEMPLATES, prefill } from "@/lib/templates"

/** ⌘K / Ctrl+K: every destination and action from the keyboard. */
export function CommandPalette({ onOpenSettings }: { onOpenSettings: () => void }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { can } = useAuth()
  const { list } = useConversations()
  const { setTheme } = useTheme()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const run = (fn: () => void) => { setOpen(false); fn() }
  const inChat = pathname === "/" || pathname.startsWith("/c/")

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Command palette" className="sm:max-w-xl"
                   description="Go anywhere, start a task, or find a conversation">
      {/* This shadcn version leaves the cmdk root to the caller; without it
          every item throws reading the store and the page goes blank. */}
      <Command>
      <CommandInput placeholder="Type a command or search conversations…" />
      <CommandList>
        <CommandEmpty>Nothing matches.</CommandEmpty>
        <CommandGroup heading="Start">
          <CommandItem onSelect={() => run(() => navigate("/"))}>
            <SquarePen /> New conversation
          </CommandItem>
          {TEMPLATES.map((t) => (
            <CommandItem key={t.cmd} value={`${t.title} /${t.cmd} ${t.hint}`}
                         onSelect={() => run(() => { if (!inChat) navigate("/"); prefill(t.prompt) })}>
              <t.icon /> <span className="shrink-0">{t.title}</span>
              <span className="min-w-0 truncate text-muted-foreground">{t.hint}</span>
              <CommandShortcut>/{t.cmd}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Go to">
          <CommandItem onSelect={() => run(() => navigate("/knowledge"))}>
            <BookOpen /> Knowledge base
          </CommandItem>
          {can("manage_users") && (
            <CommandItem onSelect={() => run(() => navigate("/admin/users"))}><Users /> Users</CommandItem>
          )}
          {can("manage_models") && (
            <CommandItem onSelect={() => run(() => navigate("/admin/models"))}><Cpu /> Models</CommandItem>
          )}
          {can("read_audit") && (
            <CommandItem onSelect={() => run(() => navigate("/admin/audit"))}><ScrollText /> Audit log</CommandItem>
          )}
          <CommandItem onSelect={() => run(onOpenSettings)}><Settings /> Settings</CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Theme">
          <CommandItem onSelect={() => run(() => setTheme("light"))}><Sun /> Light</CommandItem>
          <CommandItem onSelect={() => run(() => setTheme("dark"))}><Moon /> Dark</CommandItem>
          <CommandItem onSelect={() => run(() => setTheme("system"))}><Monitor /> Match system</CommandItem>
        </CommandGroup>
        {list.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Conversations">
              {list.map((c) => (
                // The id keeps two conversations with the same title distinct.
                <CommandItem key={c.id} value={`${c.title} ${c.id}`}
                             onSelect={() => run(() => navigate(`/c/${c.id}`))}>
                  <MessageSquare /> <span className="truncate">{c.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
      </Command>
    </CommandDialog>
  )
}
