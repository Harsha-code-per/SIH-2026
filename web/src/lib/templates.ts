import { Calculator, Code2, FileSpreadsheet, FileText, PenTool, ScanText } from "lucide-react"

/** Starting points for the tasks the workbench is built for. Reached by typing
 *  "/" in the composer or from the ⌘K palette. They only fill the composer:
 *  routing still decides the tier from the words, not from the command. */
export const TEMPLATES = [
  { cmd: "note", icon: FileText, title: "Approval note",
    hint: "A Word document checked against the SOP",
    prompt: "Write an approval note as a Word document for " },
  { cmd: "calc", icon: Calculator, title: "Calculate",
    hint: "Exact arithmetic, no model",
    prompt: "Calculate " },
  { cmd: "scan", icon: ScanText, title: "Read a scanned report",
    hint: "Attach a PDF or photo first",
    prompt: "Read the attached inspection report and list every finding with its reading and the applicable limit." },
  { cmd: "drawing", icon: PenTool, title: "Read a drawing",
    hint: "Attach a P&ID first",
    prompt: "List every equipment tag, line number and instrument on the attached drawing." },
  { cmd: "code", icon: Code2, title: "Write and run code",
    hint: "Runs in a sandbox with no network",
    prompt: "Write and run Python to " },
  { cmd: "sheet", icon: FileSpreadsheet, title: "Excel sheet",
    hint: "A spreadsheet deliverable",
    prompt: "Make an Excel sheet of " },
] as const

// Handing a template to the composer, which may not be mounted yet when the
// palette navigates to it: park the text, then announce it.
let pending: string | null = null

export function prefill(text: string) {
  pending = text
  window.dispatchEvent(new Event("workbench:prefill"))
}

export function takePrefill(): string | null {
  const t = pending
  pending = null
  return t
}
