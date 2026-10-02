import { CircleAlert, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export function EmptyState({ icon, title, children, className }: {
  icon: ReactNode
  title: string
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className)}>
      <div className="grid size-14 place-items-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-violet-300">
        {icon}
      </div>
      <p className="font-display text-lg font-semibold text-violet-100">{title}</p>
      {children && <div className="max-w-md text-sm text-violet-300/80">{children}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-4 px-6 py-12 text-center">
      <div className="grid size-14 place-items-center rounded-2xl border border-rose-400/30 bg-rose-500/10 text-rose-300">
        <CircleAlert className="size-6" strokeWidth={1.75} aria-hidden />
      </div>
      <p className="max-w-md text-sm text-violet-100">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className={cn(
          'inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white',
          'transition-colors duration-200 ease-in-out hover:bg-violet-500 active:bg-violet-700',
          'focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:ring-offset-2 focus-visible:ring-offset-void-950 focus-visible:outline-none',
        )}
      >
        <RefreshCw className="size-4" aria-hidden />
        Tentar de novo
      </button>
    </div>
  )
}
