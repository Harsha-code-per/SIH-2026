import { useId } from "react"
import { cn } from "@/lib/utils"

/** The mark: a shield with a check, stroked in the brand gradient. Inline
 *  SVG, like everything else here. */
export function BrandMark({ className }: { className?: string }) {
  const id = useId()
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke={`url(#${id})`} strokeWidth={1.9}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
         className={cn("text-brand", className)}>
      <defs>
        <linearGradient id={id} x1="4" y1="3" x2="20" y2="21" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--brand-3)" />
          <stop offset="0.5" stopColor="var(--brand)" />
          <stop offset="1" stopColor="var(--brand-2)" />
        </linearGradient>
      </defs>
      <path d="M12 2.5 4 6v6c0 4.6 3.2 8.4 8 9.5 4.8-1.1 8-4.9 8-9.5V6l-8-3.5Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  )
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <BrandMark className="size-5 shrink-0" />
      <span className="truncate text-[15px] font-semibold tracking-tight">Workbench</span>
    </div>
  )
}
