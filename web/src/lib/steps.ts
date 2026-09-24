import type { Step } from "./types"
import { TIER } from "./tiers"

/** A step in plain words: a verb, then its argument -- the way Claude writes
 *  "Searched the web · query" rather than printing a function name. */
export function describe(step: Step): { verb: string; arg?: string } {
  const d = step.detail
  const args = parseArgs(d.arguments)
  switch (step.kind) {
    case "route":
      if (step.label.startsWith("attachment")) {
        return { verb: "Inspected the attachment", arg: String(d.why ?? "") }
      }
      if (step.label.includes(" reads ")) {
        return { verb: "Split the work", arg: step.label }
      }
      if (d.tier) {
        const t = TIER[d.tier as keyof typeof TIER]
        return { verb: `Routed to ${t?.name ?? d.tier}`, arg: String(d.why ?? "") }
      }
      return { verb: step.label }
    case "tool":
      switch (step.label) {
        case "kb_search": return { verb: "Searched the SOPs", arg: str(args.query) }
        case "read_document": return { verb: "Read", arg: base(args.path) }
        case "parse_page": return { verb: "Transcribed", arg: `page ${args.page} of ${base(args.path)}` }
        case "describe_image": return { verb: "Read the drawing", arg: base(args.path) }
        case "calculate": return { verb: "Computed", arg: str(args.expression) }
        case "percent_change": return { verb: "Computed a change", arg: `${args.before} → ${args.after}` }
        case "run_python": return { verb: "Ran code in the sandbox" }
        case "write_docx": return { verb: "Wrote a Word document", arg: str(args.filename) || str(args.title) }
        case "write_xlsx": return { verb: "Wrote a spreadsheet", arg: str(args.filename) }
        default: return { verb: `Used ${step.label}` }
      }
    case "result": return { verb: step.label, arg: resultArg(d) }
    case "verify": return { verb: step.label }
    case "escalate": return { verb: "Escalated", arg: step.label }
    case "retry": return { verb: "Retried", arg: step.label }
    case "done": return { verb: step.label === "ok" ? "Finished" : `Finished: ${step.label}` }
    case "error": return { verb: "Error", arg: step.label }
    default: return { verb: step.label }
  }
}

/** One line for a whole turn, Claude-style: "Routed to Reasoning · searched
 *  the SOPs twice · computed 2 values · wrote 1 document". */
export function summarise(steps: Step[]): string {
  const tools = steps.filter((s) => s.kind === "tool").map((s) => s.label)
  const n = (name: string) => tools.filter((t) => t === name).length
  const route = steps.find((s) => s.kind === "route" && s.detail.tier)
  const parts: string[] = []
  if (route) {
    const t = TIER[route.detail.tier as keyof typeof TIER]
    parts.push(`Routed to ${t?.name ?? route.detail.tier}`)
  }
  const times = (k: number) => (k === 1 ? "once" : k === 2 ? "twice" : `${k} times`)
  if (n("kb_search")) parts.push(`searched the SOPs ${times(n("kb_search"))}`)
  const pages = n("parse_page")
  if (pages) parts.push(`transcribed ${pages} page${pages > 1 ? "s" : ""}`)
  if (n("describe_image")) parts.push("read a drawing")
  const calcs = n("calculate") + n("percent_change")
  if (calcs) parts.push(`computed ${calcs} value${calcs > 1 ? "s" : ""}`)
  const runs = n("run_python")
  if (runs) parts.push(`ran code ${times(runs)}`)
  const docs = n("write_docx") + n("write_xlsx")
  if (docs) parts.push(`wrote ${docs} document${docs > 1 ? "s" : ""}`)
  if (steps.some((s) => s.kind === "escalate")) parts.push("escalated")
  if (steps.some((s) => s.kind === "retry")) parts.push("revised its answer")
  return parts.join(" · ") || `${steps.length} step${steps.length === 1 ? "" : "s"}`
}

/** What the agent is doing right now, for the live indicator. */
export function currentActivity(steps: Step[]): string {
  const last = [...steps].reverse().find((s) => s.kind === "tool" || s.kind === "route"
                                              || s.kind === "retry" || s.kind === "escalate")
  if (!last) return "Thinking"
  const { verb, arg } = describe(last)
  return arg && last.kind === "tool" ? `${verb} · ${arg}` : verb
}

function parseArgs(raw: unknown): Record<string, unknown> {
  if (typeof raw !== "string") return {}
  try { return JSON.parse(raw) } catch { return {} }
}
const str = (v: unknown) => (typeof v === "string" ? v : "")
const base = (v: unknown) => str(v).split("/").pop() ?? ""

function resultArg(d: Record<string, unknown>): string | undefined {
  if (Array.isArray(d.cites) && d.cites.length) return String(d.cites[0])
  if (typeof d.steps === "string") return d.steps
  if (typeof d.stdout === "string" && d.stdout.trim()) return d.stdout.trim().split("\n")[0]
  if (typeof d.error === "string") return d.error
  // Tool results other than search and sandbox arrive as a printed Python
  // dict; the calculator's worked line is the part a reader wants.
  if (typeof d.output === "string") {
    const worked = d.output.match(/'steps': '([^']*)'/)?.[1]
    return worked ?? d.output.match(/'result': ([^,}]+)/)?.[1]
  }
  return undefined
}
