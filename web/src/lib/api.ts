// One fetch layer for the whole interface.
//
// The token always travels as a header, never in a URL (docs/DECISIONS.md
// D-47). That rules out EventSource and plain <a download> links, which cannot
// send headers, so both streams and downloads are read with fetch() here.

const TOKEN_KEY = "token"

let token: string | null = null
try { token = localStorage.getItem(TOKEN_KEY) } catch { /* private window */ }

let onUnauthorized: () => void = () => {}

export const auth = {
  get token() { return token },
  set(t: string | null) {
    token = t
    try {
      if (t) localStorage.setItem(TOKEN_KEY, t)
      else localStorage.removeItem(TOKEN_KEY)
    } catch { /* storage unavailable: the session still works in memory */ }
  },
  onUnauthorized(fn: () => void) { onUnauthorized = fn },
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function headers(extra?: HeadersInit): HeadersInit {
  return { ...(extra ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) }
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(path, { ...init, headers: headers(init.headers) })
  if (res.status === 401 && path !== "/api/login") {
    onUnauthorized()
    throw new ApiError(401, "Your session ended. Sign in again.")
  }
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not JSON */ }
    throw new ApiError(res.status, detail)
  }
  return res
}

export const api = {
  get: async <T>(path: string) => (await request(path)).json() as Promise<T>,
  post: async <T>(path: string, form?: Record<string, string | Blob>) =>
    (await request(path, { method: "POST", body: toForm(form) })).json() as Promise<T>,
  patch: async <T>(path: string, form: Record<string, string>) =>
    (await request(path, { method: "PATCH", body: toForm(form) })).json() as Promise<T>,
  del: async <T>(path: string) =>
    (await request(path, { method: "DELETE" })).json() as Promise<T>,

  /** Read a server-sent-event stream with auth, yielding each parsed event. */
  async *stream<E>(path: string, init: RequestInit = {}): AsyncGenerator<E> {
    const res = await request(path, init)
    if (!res.body) return
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split("\n\n")
      buffer = frames.pop() ?? ""
      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data: "))
        if (line) yield JSON.parse(line.slice(6)) as E
      }
    }
  },

  /** Download a file through fetch so the token stays out of the URL. */
  async download(path: string, filename: string) {
    const blob = await (await request(path)).blob()
    const url = URL.createObjectURL(blob)
    const a = Object.assign(document.createElement("a"), { href: url, download: filename })
    document.body.append(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
}

function toForm(fields?: Record<string, string | Blob>): FormData | undefined {
  if (!fields) return undefined
  const fd = new FormData()
  for (const [k, v] of Object.entries(fields)) fd.set(k, v)
  return fd
}
