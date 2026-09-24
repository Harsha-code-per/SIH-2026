import type { Tier } from "./types"

/** How each tier is named in the interface. The codes stay visible because the
 *  routing is the point, but people read words first. */
export const TIER: Record<Tier, { name: string; short: string; tone: string; dot: string }> = {
  // One hue per tier, used everywhere the tier appears, so the routing is
  // readable at a glance: green is no model, blue cheap, violet heavy,
  // pink and amber the two ways of seeing.
  L0:  { name: "Calculator",      short: "No model",  dot: "bg-emerald-500",
         tone: "text-emerald-600 bg-emerald-500/12 ring-1 ring-inset ring-emerald-500/25 dark:text-emerald-400" },
  L1:  { name: "Fast",            short: "Fast",      dot: "bg-sky-500",
         tone: "text-sky-600 bg-sky-500/12 ring-1 ring-inset ring-sky-500/25 dark:text-sky-400" },
  L2:  { name: "Reasoning",       short: "Reasoning", dot: "bg-violet-500",
         tone: "text-violet-600 bg-violet-500/12 ring-1 ring-inset ring-violet-500/25 dark:text-violet-300" },
  LV:  { name: "Document vision", short: "Documents", dot: "bg-fuchsia-500",
         tone: "text-fuchsia-600 bg-fuchsia-500/12 ring-1 ring-inset ring-fuchsia-500/25 dark:text-fuchsia-300" },
  LV2: { name: "Drawing vision",  short: "Drawings",  dot: "bg-amber-500",
         tone: "text-amber-600 bg-amber-500/12 ring-1 ring-inset ring-amber-500/25 dark:text-amber-300" },
}

export const IMAGE_LIKE = /\.(pdf|png|jpe?g|webp|tiff?|bmp)$/i
