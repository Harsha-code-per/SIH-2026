import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"

/** GET a path once, with reload. Enough for the admin pages; the conversation
 *  views have their own hooks because they stream. */
export function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.get<T>(path))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => { reload() }, [reload])
  return { data, error, loading, reload, setData }
}
