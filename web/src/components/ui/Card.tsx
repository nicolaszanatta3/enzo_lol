import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface CardProps {
  title?: ReactNode
  icon?: ReactNode
  aside?: ReactNode
  className?: string
  children: ReactNode
}

/** Superfície sólida pra dado (o vidro fica só no que flutua por cima). */
export function Card({ title, icon, aside, className, children }: CardProps) {
  return (
    <section
      className={cn(
        'relative rounded-2xl border border-violet-400/15 bg-void-900/85 p-4 shadow-xl shadow-black/30 sm:p-5',
        'before:pointer-events-none before:absolute before:inset-x-6 before:-top-px before:h-px',
        'before:bg-gradient-to-r before:from-transparent before:via-fuchsia-400/60 before:to-transparent',
        className,
      )}
    >
      {(title || aside) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 font-display text-sm font-semibold tracking-[0.14em] text-violet-200 uppercase">
            {icon}
            {title}
          </h3>
          {aside}
        </header>
      )}
      {children}
    </section>
  )
}
