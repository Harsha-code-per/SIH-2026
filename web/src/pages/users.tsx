import { useState } from "react"
import { Loader2, MoreHorizontal, Trash2, UserPlus } from "lucide-react"
import { toast } from "sonner"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Page, PageState, ago } from "@/components/app/page"
import { useAuth } from "@/hooks/use-auth"
import { useLoad } from "@/hooks/use-load"
import { api } from "@/lib/api"
import type { User } from "@/lib/types"

type Account = User & { created: number; last_seen: number }
interface UsersResponse { users: Account[]; roles: Record<string, string[]> }

// What each capability means to the person granting it.
const CAPABILITY: Record<string, string> = {
  run: "ask questions and run tasks",
  upload: "attach documents",
  read_kb: "search the knowledge base",
  approve: "approve notes",
  manage_kb: "rebuild the knowledge base",
  manage_users: "manage users",
  manage_models: "reload the model registry",
  read_audit: "read the audit log",
}

export function UsersPage() {
  const { user: me } = useAuth()
  const { data, error, loading, reload } = useLoad<UsersResponse>("/api/users")
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState<Account | null>(null)
  const roles = data ? Object.keys(data.roles) : []

  const setRole = async (u: Account, role: string) => {
    try {
      await api.post(`/api/users/${encodeURIComponent(u.username)}/role`, { role })
      toast.success(`${u.display || u.username} is now ${role}. Their sessions were signed out.`)
      reload()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not change role")
    }
  }

  const remove = async (u: Account) => {
    try {
      await api.del(`/api/users/${encodeURIComponent(u.username)}`)
      toast.success(`Removed ${u.display || u.username}.`)
      reload()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not remove user")
    } finally {
      setRemoving(null)
    }
  }

  return (
    <Page title="Users" description="Local accounts. Every sign-in and change is written to the audit log."
          actions={<Button size="sm" onClick={() => setAdding(true)}><UserPlus /> Add user</Button>}>
      <PageState loading={loading && !data} error={error} />
      {data && (
        <>
          <ul className="divide-y rounded-xl border bg-card">
            {data.users.map((u) => (
              <li key={u.username} className="flex items-center gap-3 px-4 py-3">
                <Avatar className="size-8">
                  <AvatarFallback className="text-xs">
                    {(u.display || u.username).split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {u.display || u.username}
                    {u.username === me?.username && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(you)</span>}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {u.username} · last seen {ago(u.last_seen)}
                  </div>
                </div>
                <Select value={u.role} onValueChange={(r) => setRole(u, r)}
                        disabled={u.username === me?.username}>
                  <SelectTrigger size="sm" className="w-32 capitalize" aria-label={`Role for ${u.username}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map((r) => <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>)}
                  </SelectContent>
                </Select>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="size-8 text-muted-foreground"
                            aria-label={`More for ${u.username}`} disabled={u.username === me?.username}>
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem variant="destructive" onClick={() => setRemoving(u)}>
                      <Trash2 /> Remove user
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>

          <h2 className="mb-3 mt-10 text-sm font-medium text-muted-foreground">Roles</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(data.roles).map(([role, caps]) => (
              <div key={role} className="rounded-xl border bg-card p-4">
                <div className="text-sm font-medium capitalize">{role}</div>
                <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {Object.keys(CAPABILITY).filter((c) => caps.includes(c))
                    .map((c) => <li key={c}>{CAPABILITY[c]}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </>
      )}

      <AddUserDialog open={adding} onOpenChange={setAdding} roles={roles} onAdded={reload} />

      <AlertDialog open={!!removing} onOpenChange={(o) => !o && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing?.display || removing?.username}?</AlertDialogTitle>
            <AlertDialogDescription>
              They are signed out at once and cannot sign in again. Their past
              actions stay in the audit log.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => removing && remove(removing)}>
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Page>
  )
}

function AddUserDialog({ open, onOpenChange, roles, onAdded }: {
  open: boolean
  onOpenChange: (o: boolean) => void
  roles: string[]
  onAdded: () => void
}) {
  const [form, setForm] = useState({ username: "", display: "", password: "", role: "engineer" })
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post("/api/users", form)
      toast.success(`Added ${form.display || form.username}.`)
      setForm({ username: "", display: "", password: "", role: "engineer" })
      onOpenChange(false)
      onAdded()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add user")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Add user</DialogTitle>
            <DialogDescription>Give them the password in person; it is never shown again.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-5">
            <div className="grid gap-1.5">
              <Label htmlFor="nu-display">Name</Label>
              <Input id="nu-display" value={form.display} onChange={set("display")} placeholder="Arun Kumar" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="nu-username">Username</Label>
                <Input id="nu-username" value={form.username} onChange={set("username")} required
                       autoComplete="off" placeholder="arun" />
              </div>
              <div className="grid gap-1.5">
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(role) => setForm((f) => ({ ...f, role }))}>
                  <SelectTrigger className="w-full capitalize"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {roles.map((r) => <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="nu-password">Password</Label>
              <Input id="nu-password" type="password" value={form.password} onChange={set("password")}
                     required minLength={8} autoComplete="new-password"
                     placeholder="At least 8 characters" />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />} Add user
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
