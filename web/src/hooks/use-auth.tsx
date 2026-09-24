import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api, auth } from "@/lib/api"
import type { User } from "@/lib/types"

interface AuthState {
  user: User | null
  /** true until the stored token has been checked against the server */
  checking: boolean
  signIn: (username: string, password: string) => Promise<void>
  signOut: (reason?: string) => void
  /** why the last session ended, shown on the sign-in screen */
  notice: string | null
  can: (capability: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [notice, setNotice] = useState<string | null>(null)

  const signOut = useCallback((reason?: string) => {
    const t = auth.token
    auth.set(null)
    setUser(null)
    setNotice(reason ?? null)
    if (t) {
      // Best effort: revoke server-side, but never block signing out on it.
      fetch("/api/logout", { method: "POST", headers: { Authorization: `Bearer ${t}` } })
        .catch(() => {})
    }
  }, [])

  useEffect(() => {
    auth.onUnauthorized(() => signOut("Your session ended. Sign in again."))
    if (!auth.token) { setChecking(false); return }
    api.get<{ user: User }>("/api/me")
      .then((r) => setUser(r.user))
      .catch(() => auth.set(null))
      .finally(() => setChecking(false))
  }, [signOut])

  const signIn = useCallback(async (username: string, password: string) => {
    const r = await api.post<{ token: string; user: User }>(
      "/api/login", { username, password })
    auth.set(r.token)
    setNotice(null)
    setUser(r.user)
  }, [])

  const can = useCallback(
    (c: string) => Boolean(user?.capabilities.includes(c)), [user])

  return (
    <AuthContext.Provider value={{ user, checking, signIn, signOut, notice, can }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth outside AuthProvider")
  return ctx
}
