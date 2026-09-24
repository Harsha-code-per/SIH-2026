import { cn } from "@/lib/utils"

/** The mark: a white shield with a check on an orange tile. Inline SVG,
 *  like everything else here. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("grid shrink-0 place-items-center rounded-md bg-brand text-brand-foreground", className)}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}
           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="size-[68%]">
        <path d="M12 2.5 4 6v6c0 4.6 3.2 8.4 8 9.5 4.8-1.1 8-4.9 8-9.5V6l-8-3.5Z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    </span>
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
