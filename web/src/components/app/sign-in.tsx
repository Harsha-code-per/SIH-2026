import { useState } from "react"
import { Loader2, Lock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { BrandMark } from "./brand"
import { useAuth } from "@/hooks/use-auth"

export function SignIn() {
  const { signIn, notice } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(username, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed")
      setPassword("")
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="relative grid min-h-svh place-items-center bg-background p-6">
      <div className="w-full max-w-[360px]">
        <div className="mb-8 flex flex-col items-center text-center">
          <BrandMark className="mb-5 size-12 rounded-xl" />
          <h1 className="text-xl font-semibold tracking-tight">Sovereign AI Workbench</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Mangalore Refinery and Petrochemicals · PS 26117
          </p>
        </div>

        <form onSubmit={submit}
              className="space-y-4 rounded-2xl border bg-card/80 p-6 shadow-sm backdrop-blur">
          {(error || notice) && (
            <p role="alert" className="rounded-lg bg-bad/10 px-3 py-2 text-sm text-bad">
              {error ?? notice}
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input id="username" autoComplete="username" autoFocus required
                   value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="current-password" required
                   value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <Button type="submit" disabled={busy}
                  className="w-full">
            {busy && <Loader2 className="animate-spin" />}
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="size-3" /> Runs on this machine. Nothing leaves the premises.
        </p>
      </div>
    </main>
  )
}
