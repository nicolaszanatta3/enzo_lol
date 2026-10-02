import { motion } from 'motion/react'
import { cn } from '../../lib/cn'

/** Barra divergente a partir de 50%: direita (verde) favorece, esquerda (rosa) atrapalha.
 *  10 pontos de diferença já enchem a metade. */
export function WinRateBar({ rate, className }: { rate: number; className?: string }) {
  const delta = rate - 0.5
  const width = `${Math.min(Math.abs(delta) / 0.1, 1) * 50}%`
  return (
    <div aria-hidden className={cn('relative h-1.5 w-20 overflow-hidden rounded-full bg-white/5', className)}>
      <div className="absolute inset-y-0 left-1/2 w-px bg-violet-300/40" />
      <motion.div
        initial={{ width: 0 }}
        animate={{ width }}
        transition={{ type: 'spring', stiffness: 120, damping: 20, delay: 0.1 }}
        className={cn(
          'absolute inset-y-0 rounded-full',
          delta >= 0 ? 'left-1/2 bg-gradient-to-r from-emerald-500 to-emerald-300' : 'right-1/2 bg-gradient-to-l from-rose-500 to-rose-300',
        )}
      />
    </div>
  )
}
