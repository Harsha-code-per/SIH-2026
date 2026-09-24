import { useCallback, useEffect, useState } from "react"

export type Theme = "light" | "dark" | "system"

function read(): Theme {
  try { return (localStorage.getItem("theme") as Theme) || "system" } catch { return "system" }
}

function apply(theme: Theme) {
  const dark = theme === "dark" ||
    (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", dark)
}

/** Light, dark, or follow the system. index.html applies it before first
 *  paint; this keeps it in step afterwards, including OS changes. */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(read)

  useEffect(() => {
    apply(theme)
    if (theme !== "system") return
    const mq = matchMedia("(prefers-color-scheme: dark)")
    const onChange = () => apply("system")
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [theme])

  const setTheme = useCallback((t: Theme) => {
    try { localStorage.setItem("theme", t) } catch { /* ignore */ }
    setThemeState(t)
  }, [])

  return { theme, setTheme }
}
