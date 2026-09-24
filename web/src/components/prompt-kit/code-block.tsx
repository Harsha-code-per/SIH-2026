"use client"

import { cn } from "@/lib/utils"
import React, { useEffect, useState } from "react"
import { createHighlighterCore, type HighlighterCore } from "shiki/core"
import { createJavaScriptRegexEngine } from "shiki/engine/javascript"

// Edited from the prompt-kit original. Its `codeToHtml` import pulled every
// grammar shiki ships -- 309 chunks, 12 MB -- and the 600 KB oniguruma WASM
// engine, for answers that contain Python, JSON and the odd shell line. Only
// those languages are bundled, with the JavaScript regex engine. It also
// hard-coded a light theme; both themes are emitted and CSS picks one.
const LANGS = ["python", "json", "bash", "yaml", "markdown", "sql", "csv"] as const
const ALIASES: Record<string, string> = { py: "python", sh: "bash", shell: "bash",
  zsh: "bash", yml: "yaml", md: "markdown" }

let highlighter: Promise<HighlighterCore> | null = null
function getHighlighter() {
  highlighter ??= createHighlighterCore({
    themes: [import("shiki/themes/github-light.mjs"), import("shiki/themes/github-dark-dimmed.mjs")],
    langs: [
      import("shiki/langs/python.mjs"), import("shiki/langs/json.mjs"),
      import("shiki/langs/bash.mjs"), import("shiki/langs/yaml.mjs"),
      import("shiki/langs/markdown.mjs"), import("shiki/langs/sql.mjs"),
      import("shiki/langs/csv.mjs"),
    ],
    engine: createJavaScriptRegexEngine(),
  })
  return highlighter
}

function resolveLang(lang?: string): string {
  const l = (lang ?? "").toLowerCase()
  const name = ALIASES[l] ?? l
  return (LANGS as readonly string[]).includes(name) ? name : "text"
}

export type CodeBlockProps = {
  children?: React.ReactNode
  className?: string
} & React.HTMLProps<HTMLDivElement>

function CodeBlock({ children, className, ...props }: CodeBlockProps) {
  return (
    <div
      className={cn(
        "not-prose flex w-full flex-col overflow-clip border",
        "border-border bg-card text-card-foreground rounded-xl",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export type CodeBlockCodeProps = {
  code: string
  language?: string
  theme?: string
  className?: string
} & React.HTMLProps<HTMLDivElement>

function CodeBlockCode({
  code,
  language = "text",
  theme: _theme,
  className,
  ...props
}: CodeBlockCodeProps) {
  const [highlightedHtml, setHighlightedHtml] = useState<string | null>(null)

  useEffect(() => {
    async function highlight() {
      if (!code) {
        setHighlightedHtml("<pre><code></code></pre>")
        return
      }

      const h = await getHighlighter()
      const html = h.codeToHtml(code, {
        lang: resolveLang(language),
        themes: { light: "github-light", dark: "github-dark-dimmed" },
        defaultColor: false,
      })
      setHighlightedHtml(html)
    }
    highlight()
  }, [code, language])

  const classNames = cn(
    "w-full overflow-x-auto text-[13px] [&>pre]:px-4 [&>pre]:py-4",
    className
  )

  // SSR fallback: render plain code if not hydrated yet
  return highlightedHtml ? (
    <div
      className={classNames}
      dangerouslySetInnerHTML={{ __html: highlightedHtml }}
      {...props}
    />
  ) : (
    <div className={classNames} {...props}>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}

export type CodeBlockGroupProps = React.HTMLAttributes<HTMLDivElement>

function CodeBlockGroup({
  children,
  className,
  ...props
}: CodeBlockGroupProps) {
  return (
    <div
      className={cn("flex items-center justify-between", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export { CodeBlockGroup, CodeBlockCode, CodeBlock }
