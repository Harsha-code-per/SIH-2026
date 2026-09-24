import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { Calculator, ClipboardCheck, Code2, FileText, PanelRight, Upload } from "lucide-react"
import { ChatContainerContent, ChatContainerRoot } from "@/components/prompt-kit/chat-container"
import { ScrollButton } from "@/components/prompt-kit/scroll-button"
import { Button } from "@/components/ui/button"
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Composer, type Attachment } from "@/components/app/composer"
import { AssistantTurn, LiveAssistant, UserBubble } from "@/components/app/thread"
import { Inspector, type InspectorSubject, type InspectorTab } from "@/components/app/inspector"
import { BrandMark } from "@/components/app/brand"
import { useAuth } from "@/hooks/use-auth"
import { useConversations } from "@/hooks/use-conversations"
import { useIsMobile } from "@/hooks/use-mobile"
import { useThread } from "@/hooks/use-thread"

const SUGGESTIONS = [
  { icon: ClipboardCheck, label: "Check a reading against the SOP",
    prompt: "Pump P-204 drive-end vibration is 8.2 mm/s RMS. What zone is that, and what does the SOP require?" },
  { icon: FileText, label: "Draft an approval note",
    prompt: "Pump P-204 drive-end vibration is 8.2 mm/s RMS, up from 6.5 mm/s last month. Check it against the SOP and produce an approval note as a Word document." },
  { icon: Code2, label: "Analyse a trend in code",
    prompt: "Write and run a python script that fits a linear trend to the readings 6.5, 7.0, 7.6, 8.2 and reports the slope in mm/s per month." },
  { icon: Calculator, label: "Run a calculation",
    prompt: "Calculate the percentage increase from 6.5 to 8.2" },
]

function pref(key: string, fallback: boolean): boolean {
  try { const v = localStorage.getItem(key); return v === null ? fallback : v === "1" } catch { return fallback }
}
function setPref(key: string, v: boolean) {
  try { localStorage.setItem(key, v ? "1" : "0") } catch { /* ignore */ }
}

export function ChatPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { list, touch } = useConversations()
  const isMobile = useIsMobile()
  const { open: sidebarOpen } = useSidebar()
  const [attachment, setAttachment] = useState<Attachment | null>(null)
  const [dragging, setDragging] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(() => pref("inspector:open", true))
  // On a phone the Inspector is a sheet over the conversation, so it opens
  // only when asked for -- never on load or when a run starts -- and closing
  // it leaves the desktop preference alone.
  const [sheetOpen, setSheetOpen] = useState(false)
  const [tab, setTab] = useState<InspectorTab>("activity")
  const [selected, setSelected] = useState<number | null>(null)
  const [highlight, setHighlight] = useState<string | null>(null)

  const thread = useThread(id ?? null, {
    // A new conversation gets its address as soon as the server names it, so a
    // reload mid-run lands back on it.
    onConversation: (cid) => navigate(`/c/${cid}`, { replace: true }),
    onTitle: (cid, title) => touch({ id: cid, title }),
  })

  // A different conversation starts with nothing selected and no attachment.
  useEffect(() => { setSelected(null); setAttachment(null) }, [id])

  const title = list.find((c) => c.id === id)?.title
  const empty = !thread.turns.length && !thread.live && !thread.loading

  const send = useCallback((prompt: string, a: Attachment | null) => {
    setSelected(null)
    // The Inspector opens when a run starts -- unless the user closed it, in
    // which case it stays closed until they open it again.
    if (!isMobile && pref("inspector:auto", true)) { setInspectorOpen(true); setTab("activity") }
    void thread.send(prompt, a?.path ?? null)
    setAttachment(null)
  }, [thread, isMobile])

  const subject: InspectorSubject | null = useMemo(() => {
    if (thread.live && selected === null) {
      // An errored run is over: the Inspector must stop saying "Working".
      return { steps: thread.live.steps, evidence: [], deliverables: [],
               live: thread.live.status === "running",
               thinking: thread.live.thinking }
    }
    const t = thread.turns[selected ?? thread.turns.length - 1]
    return t ? { steps: t.steps, decision: t.decision, evidence: t.evidence,
                 deliverables: t.deliverables, live: false } : null
  }, [thread.live, thread.turns, selected])

  const inspect = (i: number) => {
    setSelected(i); setHighlight(null)
    if (isMobile) { setSheetOpen(true); return }
    setInspectorOpen(true)
    setPref("inspector:open", true); setPref("inspector:auto", true)
  }
  const openSource = (i: number, id: string) => {
    inspect(i); setTab("sources"); setHighlight(id)
  }
  const closeInspector = () => {
    if (isMobile) { setSheetOpen(false); return }
    setInspectorOpen(false); setPref("inspector:open", false); setPref("inspector:auto", false)
  }
  const shown = isMobile ? sheetOpen : inspectorOpen
  const toggleInspector = () => (shown ? closeInspector() : inspect(selected ?? thread.turns.length - 1))

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files?.[0]
    if (f) window.dispatchEvent(new CustomEvent("workbench:file", { detail: f }))
  }

  if (thread.missing) {
    return (
      <div className="grid h-full place-items-center p-6 text-center">
        <div>
          <p className="font-medium">This conversation isn’t available.</p>
          <p className="mt-1 text-sm text-muted-foreground">It may have been deleted, or belong to someone else.</p>
          <Button className="mt-4" onClick={() => navigate("/")}>Start a new conversation</Button>
        </div>
      </div>
    )
  }

  const inspector = (
    <Inspector subject={subject} tab={tab} setTab={setTab} onClose={closeInspector}
               highlight={highlight} />
  )

  return (
    <div className="flex h-full min-h-0">
      <div className="relative flex min-w-0 flex-1 flex-col"
           onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
           onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false) }}
           onDrop={onDrop}>
        <header className="flex h-12 shrink-0 items-center gap-2 px-3">
          {(!sidebarOpen || isMobile) && <SidebarTrigger className="text-muted-foreground" />}
          <h1 className="min-w-0 truncate text-sm font-medium">{title ?? (empty ? "" : "New conversation")}</h1>
          {/* Nothing to inspect before the first turn. */}
          {!empty && <div className="ml-auto">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="size-8 text-muted-foreground"
                        onClick={toggleInspector} aria-label="Toggle Inspector"
                        aria-pressed={shown}>
                  <PanelRight className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Inspector</TooltipContent>
            </Tooltip>
          </div>}
        </header>

        {empty ? (
          <div className="ambient flex flex-1 flex-col items-center justify-center px-4 pb-16">
            <div className="w-full max-w-[680px]">
              <div className="mb-8 flex flex-col items-center gap-3 text-center">
                <BrandMark className="size-9" />
                <h2 className="text-3xl font-semibold tracking-tight">
                  Good {greeting()}, {firstName(user?.display || user?.username)}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Ask about a reading, attach a scanned report or a drawing, or have a note drafted.
                </p>
              </div>
              <Composer onSend={send} onStop={thread.stop} running={thread.running}
                        attachment={attachment} setAttachment={setAttachment} autoFocus />
              <div className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s.label} onClick={() => send(s.prompt, null)}
                          className="group flex items-center gap-3 rounded-xl border bg-card/60 px-3.5 py-3
                                     text-left text-[13px] transition-colors hover:border-ring/40 hover:bg-card">
                    <s.icon className="size-4 shrink-0 text-muted-foreground group-hover:text-brand" />
                    <span>{s.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            <ChatContainerRoot className="relative min-h-0 flex-1">
              <ChatContainerContent className="mx-auto w-full max-w-[760px] gap-8 px-4 pb-8 pt-4 md:px-6">
                {thread.turns.map((t, i) => (
                  <div key={i} className="space-y-5">
                    <UserBubble text={t.prompt} attachment={t.attachment} />
                    <AssistantTurn turn={t} onInspect={() => inspect(i)}
                                   onCite={(id) => openSource(i, id)} />
                  </div>
                ))}
                {thread.live && (
                  <div className="space-y-5">
                    <UserBubble text={thread.live.prompt} attachment={thread.live.attachment} />
                    <LiveAssistant live={thread.live} />
                  </div>
                )}
              </ChatContainerContent>
              <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
                <ScrollButton className="pointer-events-auto shadow-md" />
              </div>
            </ChatContainerRoot>
            <div className="mx-auto w-full max-w-[760px] px-4 pb-4 md:px-6">
              <Composer onSend={send} onStop={thread.stop} running={thread.running}
                        attachment={attachment} setAttachment={setAttachment} />
            </div>
          </>
        )}

        {dragging && (
          <div className="pointer-events-none absolute inset-2 z-20 grid place-items-center rounded-2xl
                          border-2 border-dashed border-brand/60 bg-background/80 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-2 text-brand">
              <Upload className="size-6" />
              <span className="text-sm font-medium">Drop a document or drawing</span>
            </div>
          </div>
        )}
      </div>

      {/* Pushes the conversation aside rather than covering it, as ChatGPT's
          Sources panel does. On a phone it becomes a sheet. */}
      {isMobile ? (
        <Sheet open={sheetOpen && !empty} onOpenChange={(o) => (o ? setSheetOpen(true) : closeInspector())}>
          <SheetContent side="bottom" className="h-[80svh] p-0">
            <SheetTitle className="sr-only">Inspector</SheetTitle>
            {inspector}
          </SheetContent>
        </Sheet>
      ) : inspectorOpen && !empty && (
        // Nothing to inspect in an empty conversation, so no panel -- the
        // reference products show nothing there either.
        <div className="w-[380px] shrink-0 xl:w-[420px]">{inspector}</div>
      )}
    </div>
  )
}

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening"
}
function firstName(s?: string) {
  return (s ?? "").split(/[\s(]/)[0] || "there"
}
