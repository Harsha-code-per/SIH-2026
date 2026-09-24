import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { ConversationSummary } from "@/lib/types"
import { useAuth } from "./use-auth"

interface ConversationsState {
  list: ConversationSummary[]
  loading: boolean
  refresh: () => Promise<void>
  rename: (id: string, title: string) => Promise<void>
  remove: (id: string) => Promise<void>
  /** Put a just-created or just-updated conversation at the top immediately,
   *  without waiting for a round trip. */
  touch: (c: Pick<ConversationSummary, "id" | "title">) => void
}

const Ctx = createContext<ConversationsState | null>(null)

export function ConversationsProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const [list, setList] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!user) { setList([]); return }
    setLoading(true)
    try {
      const r = await api.get<{ conversations: ConversationSummary[] }>("/api/conversations")
      setList(r.conversations)
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => { void refresh() }, [refresh])

  const rename = useCallback(async (id: string, title: string) => {
    const r = await api.patch<ConversationSummary>(`/api/conversations/${id}`, { title })
    setList((l) => l.map((c) => (c.id === id ? { ...c, title: r.title } : c)))
  }, [])

  const remove = useCallback(async (id: string) => {
    await api.del(`/api/conversations/${id}`)
    setList((l) => l.filter((c) => c.id !== id))
  }, [])

  const touch = useCallback((c: Pick<ConversationSummary, "id" | "title">) => {
    setList((l) => {
      const now = Date.now() / 1000
      const existing = l.find((x) => x.id === c.id)
      const updated = existing
        ? { ...existing, title: c.title, updated: now, turns: existing.turns + 1 }
        : { id: c.id, title: c.title, created: now, updated: now, turns: 1 }
      return [updated, ...l.filter((x) => x.id !== c.id)]
    })
  }, [])

  return (
    <Ctx.Provider value={{ list, loading, refresh, rename, remove, touch }}>
      {children}
    </Ctx.Provider>
  )
}

export function useConversations() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error("useConversations outside ConversationsProvider")
  return ctx
}

/** Today / Yesterday / Previous 7 days / Older, as the reference products do. */
export function groupByAge(list: ConversationSummary[]) {
  const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0)
  const day = 86400
  const t0 = startOfToday.getTime() / 1000
  const groups: [string, ConversationSummary[]][] = [
    ["Today", []], ["Yesterday", []], ["Previous 7 days", []], ["Older", []],
  ]
  for (const c of list) {
    const i = c.updated >= t0 ? 0 : c.updated >= t0 - day ? 1
      : c.updated >= t0 - 7 * day ? 2 : 3
    groups[i][1].push(c)
  }
  return groups.filter(([, items]) => items.length)
}
