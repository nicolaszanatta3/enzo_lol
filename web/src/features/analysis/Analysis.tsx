import { AnimatePresence, motion } from 'motion/react'
import { Ban, Gem, Layers, Swords, type LucideIcon } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { ErrorState } from '../../components/ui/States'
import { useApi, type BanRow, type BuildData, type Champion, type CountersData, type Position } from '../../lib/api'
import { cn } from '../../lib/cn'
import { BansPanel, BansSkeleton } from './BansPanel'
import { BuildPanel, BuildSkeleton } from './BuildPanel'
import { ChampionHero } from './ChampionHero'
import { CountersPanel, CountersSkeleton } from './CountersPanel'
import { RunesPanel, RunesSkeleton } from './RunesPanel'

export type Tab = 'counters' | 'bans' | 'build' | 'runes'

const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: 'counters', label: 'Counters', icon: Swords },
  { id: 'bans', label: 'Quem banir', icon: Ban },
  { id: 'build', label: 'Build', icon: Layers },
  { id: 'runes', label: 'Runas', icon: Gem },
]

interface AnalysisProps {
  champion: Champion
  position: Position
  tab: Tab
  onTabChange: (tab: Tab) => void
}

export function Analysis({ champion, position, tab, onTabChange: setTab }: AnalysisProps) {
  // As três buscas saem juntas: trocar de aba depois é instantâneo.
  const base = `${champion.id}/${position}`
  const counters = useApi<CountersData>(`/api/counters/${base}`)
  const bans = useApi<BanRow[]>(`/api/bans/${base}`)
  const build = useApi<BuildData>(`/api/build/${base}`)

  // Teclas 1-4 trocam de aba (fora de campos de texto).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.metaKey || event.ctrlKey || event.altKey) return
      const index = Number(event.key) - 1
      if (TABS[index]) setTab(TABS[index].id)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setTab])

  const loading = { counters: counters.loading, bans: bans.loading, build: build.loading, runes: build.loading }

  let content: ReactNode
  if (tab === 'counters') {
    content = counters.error ? <ErrorState message={counters.error} onRetry={counters.retry} />
      : counters.data ? <CountersPanel data={counters.data} championName={champion.name} /> : <CountersSkeleton />
  } else if (tab === 'bans') {
    content = bans.error ? <ErrorState message={bans.error} onRetry={bans.retry} />
      : bans.data ? <BansPanel bans={bans.data} championName={champion.name} /> : <BansSkeleton />
  } else {
    content = build.error ? <ErrorState message={build.error} onRetry={build.retry} />
      : !build.data ? (tab === 'build' ? <BuildSkeleton /> : <RunesSkeleton />)
      : tab === 'build' ? <BuildPanel build={build.data} /> : <RunesPanel runes={build.data.runes} />
  }

  return (
    <div className="space-y-5">
      <ChampionHero champion={champion} position={position} stats={build.data?.stats} />

      <div role="tablist" aria-label="Análise" className="sticky top-3 z-30 grid grid-cols-4 gap-1 rounded-2xl border border-white/10 bg-void-900/70 p-1.5 shadow-xl shadow-black/40 backdrop-blur-md">
        {TABS.map(({ id, label, icon: Icon }, index) => {
          const active = tab === id
          return (
            <button
              key={id}
              type="button"
              role="tab"
              id={`tab-${id}`}
              aria-selected={active}
              aria-controls="analysis-panel"
              onClick={() => setTab(id)}
              className={cn(
                'relative flex items-center justify-center gap-2 rounded-xl px-2 py-2.5 text-sm font-semibold',
                'transition-colors duration-200 ease-in-out focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none',
                active ? 'text-white' : 'text-violet-300/80 hover:bg-white/5 hover:text-violet-100 active:bg-white/10',
              )}
            >
              {active && (
                <motion.span
                  layoutId="tab-pill"
                  transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  className="absolute inset-0 rounded-xl bg-gradient-to-br from-violet-600/90 to-fuchsia-600/80 shadow-lg shadow-fuchsia-600/30 ring-1 ring-fuchsia-300/30"
                />
              )}
              <span className="relative hidden font-display text-xs text-violet-300/60 tabular-nums sm:inline">0{index + 1}</span>
              <Icon className="relative size-4" aria-hidden />
              <span className="sr-only sm:not-sr-only sm:relative">{label}</span>
              {loading[id] && (
                <span aria-hidden className="relative size-1.5 rounded-full bg-fuchsia-400 motion-safe:animate-pulse" />
              )}
            </button>
          )
        })}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={`${tab}-${base}`}
          id="analysis-panel"
          role="tabpanel"
          aria-labelledby={`tab-${tab}`}
          aria-busy={loading[tab]}
          initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
          transition={{ duration: 0.22, ease: 'easeOut' }}
        >
          {content}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
