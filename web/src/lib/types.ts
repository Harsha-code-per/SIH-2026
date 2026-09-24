// Shapes the backend actually returns. Kept in one place so a change in
// app/main.py has exactly one file to update on this side.

export type Tier = "L0" | "L1" | "L2" | "LV" | "LV2"

export interface Decision {
  tier: Tier
  model_id: string | null
  model_name: string | null
  tool: string | null
  max_tokens: number
  rule: string
  why: string
  features: {
    task: string
    has_image: boolean
    image_kind: string | null
    input_tokens: number
    needs_tools: boolean
  }
  mode: string
  escalates_to: Tier | null
}

export type StepKind =
  | "route" | "tool" | "result" | "verify" | "escalate" | "retry" | "done" | "error"

export interface Step {
  n: number
  kind: StepKind
  label: string
  detail: Record<string, unknown>
  ts: number
}

export interface Passage {
  id: string
  cite: string
  score: number
  text: string
}

export interface Deliverable {
  path: string
  bytes: number
  download: string
}

export type Verdict =
  | "ok" | "uncited" | "invented-citation" | "fabricated-output" | "ungrounded"
  | "sandbox-failed" | "malformed" | "empty" | "truncated" | "step-limit" | "failed"

export interface Turn {
  prompt: string
  answer: string
  evidence: Passage[]
  deliverables: Deliverable[]
  attachment: string | null
  decision: Decision | Record<string, never>
  steps: Step[]
  verdict: Verdict | null
  ts: number
  /** the model's own reasoning; absent on turns saved before it was kept */
  thinking?: string
}

export interface ConversationSummary {
  id: string
  title: string
  created: number
  updated: number
  turns: number
}

export interface Conversation extends Omit<ConversationSummary, "turns"> {
  turns: Turn[]
}

export interface User {
  username: string
  role: "engineer" | "approver" | "admin"
  display: string
  capabilities: string[]
}

export interface Egress {
  mode: string
  status: string
  allowlist: string[]
  allowed_count: number
  blocked_count: number
  leaked_count: number
  observed: boolean
  enforced: boolean
  enforcement: string
  contained: boolean
  events: { ts: number; dst: string; verdict: string; detail?: string }[]
}

export interface ModelInfo {
  id: string
  tier: Tier
  caps: string[]
  name: string
  why: string
  max_tokens: number | null
  modes: Record<string, string | null>
}

export interface Status {
  mode: string
  endpoint: string
  egress: Egress
  models: ModelInfo[]
  rules: { name: string; why: string; if: Record<string, unknown>; then: { tier?: Tier; tool?: string } }[]
}

// Events on the /api/run stream.
export type RunEvent =
  | { type: "conversation"; id: string }
  | ({ type: "step" } & Step)
  | ({ type: "final"; conversation: string; title: string; answer: string;
       decision: Decision; evidence: Passage[]; deliverables: Deliverable[];
       verdict: Verdict; steps: Step[]; thinking: string })
  | { type: "error"; error: string }
  // Streaming (phase G): the answer as it arrives, the model's reasoning, and
  // a withdrawal when shown text is superseded -- with the failed check as the
  // reason, or no reason for narration before a tool call.
  | { type: "token"; text: string }
  | { type: "thinking"; text: string }
  | { type: "answer_reset"; reason: string }
