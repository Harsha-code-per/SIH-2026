import { createContext, useContext, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { Egress } from "@/lib/types"
import { useAuth } from "./use-auth"

type EgressEvent = Egress["events"][number]
type Frame = ({ type: "snapshot" } & Egress) | ({ type: "egress" } & EgressEvent)

const Ctx = createContext<Egress | null>(null)

/** The containment state, kept live for the whole session.
 *
 *  Green is only ever shown when the backend itself says `contained` -- which
 *  requires enforcement detected, an observer running and zero leaks
 *  (docs/DECISIONS.md D-8). The interface never infers it.
 */
export function ContainmentProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const [state, setState] = useState<Egress | null>(null)

  useEffect(() => {
    if (!user) { setState(null); return }
    const ctrl = new AbortController()
    let delay = 1000

    const connect = async () => {
      while (!ctrl.signal.aborted) {
        try {
          for await (const f of api.stream<Frame>("/api/egress/stream",
                                                   { signal: ctrl.signal })) {
            delay = 1000
            if (f.type === "snapshot") {
              const { type: _t, ...snap } = f
              setState(snap)
            } else {
              const { type: _t, ...ev } = f
              setState((s) => s && {
                ...s,
                events: [...s.events, ev].slice(-60),
                blocked_count: s.blocked_count + (ev.verdict === "BLOCKED" ? 1 : 0),
                allowed_count: s.allowed_count + (ev.verdict === "ALLOWED" ? 1 : 0),
                leaked_count: s.leaked_count + (ev.verdict === "LEAKED" ? 1 : 0),
                contained: s.contained && ev.verdict !== "LEAKED",
              })
            }
          }
        } catch {
          if (ctrl.signal.aborted) return
        }
        // The stream dropped (restart, network). Reconnect with backoff; the
        // next snapshot restores the true state rather than a guessed one.
        await new Promise((r) => setTimeout(r, delay))
        delay = Math.min(delay * 2, 15000)
      }
    }
    void connect()
    return () => ctrl.abort()
  }, [user])

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>
}

export const useContainment = () => useContext(Ctx)
