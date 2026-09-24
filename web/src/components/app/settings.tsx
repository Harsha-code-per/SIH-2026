import { useEffect, useState } from "react"
import { Loader2, Monitor, Moon, Sun } from "lucide-react"
import { toast } from "sonner"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/hooks/use-auth"
import { type Theme, useTheme } from "@/hooks/use-theme"
import { api } from "@/lib/api"
import type { Status } from "@/lib/types"
import { cn } from "@/lib/utils"

export function SettingsDialog({ open, onOpenChange }: {
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const { user, signOut } = useAuth()
  const { theme, setTheme } = useTheme()
  const [status, setStatus] = useState<Status | null>(null)
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (open) api.get<Status>("/api/status").then(setStatus).catch(() => {})
  }, [open])

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post("/api/me/password", { current, new: next })
      toast.success("Password changed. Sign in again with the new one.")
      setCurrent(""); setNext("")
      // Changing a password invalidates every token this user holds (D-39).
      signOut("Password changed. Sign in with your new password.")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not change password")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>Signed in as {user?.display || user?.username}, {user?.role}.</DialogDescription>
        </DialogHeader>
        <Tabs defaultValue="appearance">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="appearance">Appearance</TabsTrigger>
            <TabsTrigger value="account">Account</TabsTrigger>
            <TabsTrigger value="about">About</TabsTrigger>
          </TabsList>

          <TabsContent value="appearance" className="pt-3">
            <Label className="mb-2 block">Theme</Label>
            <div className="grid grid-cols-3 gap-2">
              {([["light", Sun], ["dark", Moon], ["system", Monitor]] as [Theme, typeof Sun][]).map(([t, Icon]) => (
                <button key={t} onClick={() => setTheme(t)} aria-pressed={theme === t}
                        className={cn("flex flex-col items-center gap-2 rounded-xl border p-3 text-sm capitalize transition-colors",
                                      theme === t ? "border-ring bg-accent" : "hover:bg-accent/50")}>
                  <Icon className="size-4" /> {t}
                </button>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="account" className="pt-3">
            <form onSubmit={changePassword} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="cur">Current password</Label>
                <Input id="cur" type="password" autoComplete="current-password" required
                       value={current} onChange={(e) => setCurrent(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="new">New password</Label>
                <Input id="new" type="password" autoComplete="new-password" required minLength={8}
                       value={next} onChange={(e) => setNext(e.target.value)} />
                <p className="text-xs text-muted-foreground">At least 8 characters. You will be signed out everywhere.</p>
              </div>
              <Button type="submit" disabled={busy || next.length < 8}>
                {busy && <Loader2 className="animate-spin" />} Change password
              </Button>
            </form>
          </TabsContent>

          <TabsContent value="about" className="pt-3">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Problem statement</dt><dd>SIH 2026 · PS 26117 · MRPL</dd>
              <dt className="text-muted-foreground">Mode</dt><dd className="capitalize">{status?.mode ?? "…"}</dd>
              <dt className="text-muted-foreground">Inference</dt>
              <dd className="truncate font-mono text-xs leading-5">{status ? new URL(status.endpoint).host : "…"}</dd>
              <dt className="text-muted-foreground">Models</dt><dd>{status?.models.length ?? "…"} registered</dd>
              <dt className="text-muted-foreground">Containment</dt>
              <dd>{status ? (status.egress.contained ? "Contained" : status.egress.enforced ? "Unverified" : "Not enforced") : "…"}</dd>
            </dl>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
