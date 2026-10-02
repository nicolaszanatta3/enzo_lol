import { cn } from '../../lib/cn'

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        'rounded-lg bg-[linear-gradient(90deg,var(--color-void-800)_0%,var(--color-void-600)_50%,var(--color-void-800)_100%)]',
        'bg-[length:200%_100%] motion-safe:animate-shimmer',
        className,
      )}
    />
  )
}
