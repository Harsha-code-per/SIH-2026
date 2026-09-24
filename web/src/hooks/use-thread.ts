import { useCallback, useEffect, useRef, useState } from "react"
import { api, ApiError } from "@/lib/api"
import type { Conversation, RunEvent, Step, Turn } from "@/lib/types"

export interface LiveTurn {
  prompt: string
  attachment: string | null
  steps: Step[]
  /** answer text streamed so far */
  text: string
  /** the model's reasoning streamed so far; shown in the Inspector, not kept */
  thinking: string
  /** why the last answer was withdrawn, while its replacement streams */
  revision: string | null
  /** true while the latest thing to arrive was reasoning */
  thinkingNow: boolean
  status: "running" | "error"
  error?: string
  startedAt: number
}

/** One conversation: its completed turns from the server, plus at most one
 *  turn in flight whose steps arrive over the stream. */
export function useThread(conversationId: string | null, callbacks: {
  onConversation?: (id: string) => void
  onTitle?: (id: string, title: string) => void
} = {}) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [live, setLive] = useState<LiveTurn | null>(null)
  const [loading, setLoading] = useState(false)
  const [missing, setMissing] = useState(false)
  const abort = useRef<AbortController | null>(null)
  // The id the stream reported for a new conversation. Loading it again when
  // the URL catches up would clobber the turn we just appended.
  const created = useRef<string | null>(null)
  const cb = useRef(callbacks)
  cb.current = callbacks

  useEffect(() => {
    setMissing(false)
    // The conversation this instance just created: the server named it while
    // the first turn was still running. Keep everything; reloading would
    // replace the live turn with a conversation that has no turns saved yet.
    if (conversationId && conversationId === created.current) return
    // Anywhere else is a different conversation: stop what was running here
    // and start clean.
    abort.current?.abort()
    abort.current = null
    created.current = null
    setLive(null)
    setTurns([])
    if (!conversationId) return
    let cancelled = false
    setLoading(true)
    api.get<Conversation>(`/api/conversations/${conversationId}`)
      .then((c) => { if (!cancelled) setTurns(c.turns) })
      .catch((e) => {
        // Another user's id and a deleted one both read as absent.
        if (!cancelled && e instanceof ApiError && e.status === 404) setMissing(true)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [conversationId])

  const send = useCallback(async (prompt: string, attachment: string | null) => {
    abort.current?.abort()
    const ctrl = new AbortController()
    abort.current = ctrl
    setLive({ prompt, attachment, steps: [], text: "", thinking: "", revision: null, thinkingNow: false,
              status: "running", startedAt: Date.now() })

    const form = new FormData()
    form.set("prompt", prompt)
    if (conversationId) form.set("conversation", conversationId)
    if (attachment) form.set("attachment", attachment)

    try {
      for await (const e of api.stream<RunEvent>("/api/run",
                                                  { method: "POST", body: form, signal: ctrl.signal })) {
        if (e.type === "conversation") {
          if (!conversationId) {
            created.current = e.id
            cb.current.onConversation?.(e.id)
          }
        } else if (e.type === "step") {
          const { type: _t, ...step } = e
          setLive((l) => l && { ...l, steps: [...l.steps, step], thinkingNow: false })
        } else if (e.type === "token") {
          setLive((l) => l && { ...l, text: l.text + e.text, thinkingNow: false })
        } else if (e.type === "thinking") {
          setLive((l) => l && { ...l, thinking: l.thinking + e.text, thinkingNow: true })
        } else if (e.type === "answer_reset") {
          setLive((l) => l && { ...l, text: "", revision: e.reason || l.revision })
        } else if (e.type === "final") {
          setTurns((t) => [...t, {
            prompt, attachment, answer: e.answer, evidence: e.evidence,
            deliverables: e.deliverables, decision: e.decision, steps: e.steps,
            verdict: e.verdict, ts: Date.now() / 1000,
          }])
          setLive(null)
          cb.current.onTitle?.(e.conversation, e.title)
        } else if (e.type === "error") {
          setLive((l) => l && { ...l, status: "error", error: e.error })
        }
      }
    } catch (err) {
      if (ctrl.signal.aborted) {
        setLive((l) => l && { ...l, status: "error", error: "Stopped." })
      } else {
        setLive((l) => l && { ...l, status: "error",
                              error: err instanceof Error ? err.message : String(err) })
      }
    }
  }, [conversationId])

  const stop = useCallback(() => abort.current?.abort(), [])

  return { turns, live, loading, missing, send, stop, running: live?.status === "running" }
}
