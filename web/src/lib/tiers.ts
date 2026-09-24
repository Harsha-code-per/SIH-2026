import type { Tier } from "./types"

/** How each tier is named in the interface. The codes stay visible because the
 *  routing is the point, but people read words first. */
// One neutral style for every tier: the code and the name tell them apart,
// and colour is kept for the accent and for status.
const CHIP = "text-foreground bg-muted ring-1 ring-inset ring-border"
const DOT = "bg-brand"

export const TIER: Record<Tier, { name: string; short: string; tone: string; dot: string }> = {
  L0:  { name: "Calculator",      short: "No model",  tone: CHIP, dot: DOT },
  L1:  { name: "Fast",            short: "Fast",      tone: CHIP, dot: DOT },
  L2:  { name: "Reasoning",       short: "Reasoning", tone: CHIP, dot: DOT },
  LV:  { name: "Document vision", short: "Documents", tone: CHIP, dot: DOT },
  LV2: { name: "Drawing vision",  short: "Drawings",  tone: CHIP, dot: DOT },
}

export const IMAGE_LIKE = /\.(pdf|png|jpe?g|webp|tiff?|bmp)$/i
