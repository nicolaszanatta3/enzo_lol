import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

/** Balão em vidro no hover/foco. O filho focável recebe o aria-label. */
export function Tooltip({ content, children, className }: { content: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span className={cn('group/tip relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute bottom-full left-1/2 z-40 mb-2 w-max max-w-64 -translate-x-1/2 translate-y-1',
          'rounded-xl border border-white/10 bg-void-800/80 px-3 py-2 text-left text-xs leading-relaxed text-violet-100',
          'opacity-0 shadow-xl shadow-black/50 backdrop-blur-md transition duration-150 ease-out',
          'group-hover/tip:translate-y-0 group-hover/tip:opacity-100 group-focus-within/tip:translate-y-0 group-focus-within/tip:opacity-100',
        )}
      >
        {content}
      </span>
    </span>
  )
}
