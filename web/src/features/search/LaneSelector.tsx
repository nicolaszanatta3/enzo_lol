import { motion } from 'motion/react'
import type { Champion, Position } from '../../lib/api'
import { cn } from '../../lib/cn'
import { pct } from '../../lib/format'
import { LANES } from '../../lib/lanes'

interface LaneSelectorProps {
  value: Position | null
  champion: Champion | null
  onChange: (position: Position) => void
}

export function LaneSelector({ value, champion, onChange }: LaneSelectorProps) {
  return (
    <div role="radiogroup" aria-label="Rota" className="grid grid-cols-5 gap-1.5 rounded-2xl border border-violet-400/15 bg-void-900/70 p-1.5">
      {LANES.map(({ id, label, icon: Icon }) => {
        const active = value === id
        const rate = champion?.lanes[id] ?? null
        const rare = rate !== null && rate < 0.03
        return (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(id)}
            className={cn(
              'group relative flex flex-col items-center gap-1 rounded-xl px-1 py-2.5 text-xs font-medium sm:flex-row sm:justify-center sm:gap-2 sm:px-3 sm:text-sm',
              'transition-colors duration-200 ease-in-out focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none',
              active ? 'text-white' : 'text-violet-300/80 hover:bg-white/5 hover:text-violet-100 active:bg-white/10',
              rare && !active && 'opacity-55',
            )}
          >
            {active && (
              <motion.span
                layoutId="lane-pill"
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                className="absolute inset-0 rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-600 shadow-lg shadow-fuchsia-600/30"
              />
            )}
            <Icon className="relative size-4 transition-transform duration-200 group-hover:scale-110" aria-hidden />
            <span className="relative">{label}</span>
            {rate !== null && (
              <span className={cn('relative text-[10px] tabular-nums sm:text-xs', active ? 'text-violet-100/90' : 'text-violet-400/70')}>
                {rate > 0 ? pct(rate) : '—'}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
