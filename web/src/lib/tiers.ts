import type { Tier } from "./types"

/** How each tier is named in the interface. The codes stay visible because the
 *  routing is the point, but people read words first. */
export const TIER: Record<Tier, { name: string; short: string; tone: string }> = {
  L0:  { name: "Calculator",      short: "No model",  tone: "text-ok bg-ok/10" },
  L1:  { name: "Fast",            short: "Fast",      tone: "text-brand bg-brand/10" },
  L2:  { name: "Reasoning",       short: "Reasoning", tone: "text-warn bg-warn/10" },
  LV:  { name: "Document vision", short: "Documents", tone: "text-chart-5 bg-chart-5/10" },
  LV2: { name: "Drawing vision",  short: "Drawings",  tone: "text-chart-5 bg-chart-5/10" },
}

export const IMAGE_LIKE = /\.(pdf|png|jpe?g|webp|tiff?|bmp)$/i
