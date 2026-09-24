import { useEffect, useRef, useState } from "react"
import { ArrowUp, Check, ChevronDown, FileText, Image as ImageIcon, Loader2, Paperclip, Sparkles, Square, X } from "lucide-react"
import { toast } from "sonner"
import {
  PromptInput, PromptInputAction, PromptInputActions, PromptInputTextarea,
} from "@/components/prompt-kit/prompt-input"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useLoad } from "@/hooks/use-load"
import { api } from "@/lib/api"
import { TEMPLATES, takePrefill } from "@/lib/templates"
import { IMAGE_LIKE, TIER } from "@/lib/tiers"
import type { Decision, Status } from "@/lib/types"
import { cn } from "@/lib/utils"

export interface Attachment { path: string; name: string; bytes: number }

export function Composer({ onSend, onStop, running, attachment, setAttachment, autoFocus, className,
                           model, onModelChange }: {
  onSend: (prompt: string, attachment: Attachment | null) => void
  /** a registry model id, or null for automatic routing */
  model: string | null
  onModelChange: (id: string | null) => void
  onStop: () => void
  running: boolean
  attachment: Attachment | null
  setAttachment: (a: Attachment | null) => void
  autoFocus?: boolean
  className?: string
}) {
  const [value, setValue] = useState("")
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<Decision | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const [pick, setPick] = useState(0)

  // Slash commands: "/" alone, or "/no", lists the templates that match.
  const slash = /^\/(\w*)$/.exec(value)
  const commands = slash ? TEMPLATES.filter((t) => t.cmd.startsWith(slash[1].toLowerCase())) : []
  const active = Math.min(pick, commands.length - 1)

  const fill = (text: string) => {
    setValue(text)
    setPick(0)
    requestAnimationFrame(() => {
      const ta = boxRef.current?.querySelector("textarea")
      ta?.focus()
      ta?.setSelectionRange(text.length, text.length)
    })
  }

  // A template chosen from the palette, possibly before this mounted.
  useEffect(() => {
    const take = () => { const t = takePrefill(); if (t) fill(t) }
    take()
    window.addEventListener("workbench:prefill", take)
    return () => window.removeEventListener("workbench:prefill", take)
  }, [])

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!commands.length) return
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      const step = e.key === "ArrowDown" ? 1 : -1
      setPick((active + step + commands.length) % commands.length)
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault()
      fill(commands[active].prompt)
    } else if (e.key === "Escape") {
      e.preventDefault()
      setValue("")
    }
  }

  // Routing preview. The reference products hand the user a model picker; this
  // one routes by itself and shows where the request will go before it is sent.
  useEffect(() => {
    const prompt = value.trim()
    // A chosen model needs no preview; the choice is the answer.
    if (model) { setPreview(null); return }
    // A bare "/cmd" is the slash menu, not a request; "/" alone routes as
    // arithmetic and would preview "No model".
    if (!prompt || /^\/\w*$/.test(prompt)) { setPreview(null); return }
    const t = setTimeout(() => {
      api.post<Decision>("/api/route", {
        prompt,
        has_image: String(Boolean(attachment && IMAGE_LIKE.test(attachment.name))),
      }).then(setPreview).catch(() => setPreview(null))
    }, 350)
    return () => clearTimeout(t)
  }, [value, attachment, model])

  const send = () => {
    const prompt = value.trim()
    if (!prompt || running || uploading) return
    onSend(prompt, attachment)
    setValue("")
    setPreview(null)
  }

  const upload = async (file: File) => {
    if (file.size > 32 * 1024 * 1024) { toast.error("Files are limited to 32 MB."); return }
    setUploading(true)
    try {
      const r = await api.post<{ path: string; bytes: number }>("/api/upload", { file })
      setAttachment({ path: r.path, name: file.name, bytes: r.bytes })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  // Expose uploads to the page, which accepts a drop anywhere.
  useEffect(() => {
    const onDrop = (e: Event) => upload((e as CustomEvent<File>).detail)
    window.addEventListener("workbench:file", onDrop)
    return () => window.removeEventListener("workbench:file", onDrop)
  })

  const tier = preview ? TIER[preview.tier] : null
  const status = useLoad<Status>("/api/status")
  const models = status.data?.models ?? []
  const chosen = models.find((m) => m.id === model) ?? null
  // A remembered model that has since left models.yaml would be refused by
  // the server; fall back to Auto instead.
  useEffect(() => {
    if (model && status.data && !chosen) onModelChange(null)
  }, [model, status.data, chosen, onModelChange])

  return (
    <div ref={boxRef} className={cn("relative w-full", className)}>
      {commands.length > 0 && (
        <div role="listbox" aria-label="Commands"
             className="absolute inset-x-0 bottom-full z-20 mb-2 overflow-hidden rounded-xl border bg-popover p-1 shadow-lg">
          {commands.map((t, i) => (
            <button key={t.cmd} role="option" aria-selected={i === active} type="button"
                    onMouseEnter={() => setPick(i)} onMouseDown={(e) => { e.preventDefault(); fill(t.prompt) }}
                    className={cn("flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left",
                                  i === active && "bg-accent")}>
              <t.icon className="size-4 shrink-0 text-muted-foreground" />
              <span className="text-sm font-medium">{t.title}</span>
              <span className="min-w-0 truncate text-xs text-muted-foreground">{t.hint}</span>
              <span className="ml-auto font-mono text-xs text-muted-foreground">/{t.cmd}</span>
            </button>
          ))}
        </div>
      )}
      <PromptInput value={value} onValueChange={setValue} onSubmit={send}
                   isLoading={running} maxHeight={220}
                   className="glow-focus rounded-2xl border-border bg-card/90 p-2 shadow-lg shadow-black/5
                              backdrop-blur transition-[box-shadow,border-color]">
        {(attachment || uploading) && (
          <div className="mx-1 mb-1 mt-0.5 flex">
            <div className="flex max-w-full items-center gap-2 rounded-xl border bg-muted/60 py-1.5 pl-2.5 pr-1.5">
              {uploading ? <Loader2 className="size-4 animate-spin text-muted-foreground" />
                : attachment && IMAGE_LIKE.test(attachment.name) && !attachment.name.endsWith(".pdf")
                  ? <ImageIcon className="size-4 text-brand" /> : <FileText className="size-4 text-brand" />}
              <span className="min-w-0 truncate text-[13px] font-medium">
                {uploading ? "Uploading…" : attachment!.name}
              </span>
              {attachment && (
                <span className="tabular shrink-0 text-xs text-muted-foreground">
                  {(attachment.bytes / 1024).toFixed(0)} KB
                </span>
              )}
              {attachment && (
                <button onClick={(e) => { e.stopPropagation(); setAttachment(null) }}
                        className="rounded-md p-0.5 text-muted-foreground hover:bg-background hover:text-foreground"
                        aria-label="Remove attachment">
                  <X className="size-3.5" />
                </button>
              )}
            </div>
          </div>
        )}

        <PromptInputTextarea autoFocus={autoFocus} onKeyDown={onKeyDown}
          aria-label="Message"
          placeholder="Ask about a reading, a document or a drawing — / for tasks"
          // dark:bg-transparent: shadcn's textarea sets dark:bg-input/30, which
          // outranks a plain bg-transparent and drew a box inside the composer.
          className="px-2 text-[15px] placeholder:text-muted-foreground/70 dark:bg-transparent" />

        <PromptInputActions className="justify-between px-1 pt-1">
          <div className="flex items-center gap-1">
            <input ref={fileRef} type="file" hidden
                   accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.txt,.md"
                   onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            <PromptInputAction tooltip="Attach a document or drawing">
              <Button variant="ghost" size="icon" className="size-8 rounded-full text-muted-foreground"
                      onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
                      aria-label="Attach a file" disabled={uploading}>
                <Paperclip className="size-4" />
              </Button>
            </PromptInputAction>
          </div>

          <div className="flex items-center gap-2">
            {/* Automatic routing is the default; every model in the registry
                can still be picked by hand. The list comes from models.yaml,
                so a new model appears here without a code change. */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" aria-label="Choose model"
                  className={cn(
                    "inline-flex h-7 select-none items-center gap-1.5 rounded-full px-2.5 text-xs font-medium transition-colors",
                    chosen ? TIER[chosen.tier].tone
                      : tier ? tier.tone
                      : "bg-brand/10 text-brand ring-1 ring-inset ring-brand/20 hover:bg-brand/15")}>
                  {chosen ? <span className={cn("size-1.5 rounded-full", TIER[chosen.tier].dot)} />
                    : <Sparkles className="size-3" />}
                  {chosen ? TIER[chosen.tier].name : <>Auto{tier && <span className="opacity-80">· {tier.short}</span>}</>}
                  <ChevronDown className="size-3 opacity-70" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="end" className="w-80 p-1.5">
                <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">Model</DropdownMenuLabel>
                <DropdownMenuItem onSelect={() => onModelChange(null)} className="items-start gap-3 py-2">
                  <span className="bg-brand-gradient mt-0.5 grid size-6 shrink-0 place-items-center rounded-md text-white">
                    <Sparkles className="size-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">Auto <span className="font-normal text-muted-foreground">· recommended</span></span>
                    <span className="block text-xs text-muted-foreground">
                      {preview ? <>This request → <span className="font-medium text-foreground">{TIER[preview.tier].name}</span>. {preview.why}</>
                        : "Picks the right model for each request, and says why."}
                    </span>
                  </span>
                  {!model && <Check className="mt-1 size-4 text-brand" />}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                {models.map((m) => (
                  <DropdownMenuItem key={m.id} onSelect={() => onModelChange(m.id)} className="items-start gap-3 py-2">
                    <span className={cn("mt-0.5 grid size-6 shrink-0 place-items-center rounded-md font-mono text-[10px] font-bold", TIER[m.tier].tone)}>
                      {m.tier}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{TIER[m.tier].name}</span>
                      <span className="block truncate font-mono text-[11px] text-muted-foreground">{m.name}</span>
                    </span>
                    {model === m.id && <Check className="mt-1 size-4 text-brand" />}
                  </DropdownMenuItem>
                ))}
                <p className="px-2 pb-1 pt-2 text-[11px] leading-snug text-muted-foreground">
                  A model you pick is still checked, and escalated if its answer fails.
                </p>
              </DropdownMenuContent>
            </DropdownMenu>

            {running ? (
              <Button size="icon" variant="secondary" onClick={onStop}
                      className="size-8 rounded-full" aria-label="Stop">
                <Square className="size-3 fill-current" />
              </Button>
            ) : (
              <Button size="icon" onClick={send} disabled={!value.trim() || uploading}
                      className="bg-brand-gradient size-8 rounded-full text-white shadow-md shadow-brand/30
                                 transition-transform hover:scale-105 disabled:bg-none disabled:bg-muted
                                 disabled:text-muted-foreground disabled:shadow-none" aria-label="Send">
                <ArrowUp className="size-4" />
              </Button>
            )}
          </div>
        </PromptInputActions>
      </PromptInput>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">
        Answers are checked against your documents before they are shown. Review before you sign.
      </p>
    </div>
  )
}
