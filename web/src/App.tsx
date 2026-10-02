import { AnimatePresence, LayoutGroup, motion, MotionConfig } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { Background } from './components/Background'
import { ErrorState } from './components/ui/States'
import { Analysis, type Tab } from './features/analysis/Analysis'
import { ChampionSearch } from './features/search/ChampionSearch'
import { LaneSelector } from './features/search/LaneSelector'
import { useApi, type Champion, type Position } from './lib/api'
import { LANES, mainLane } from './lib/lanes'

// Campeão e rota ficam na URL (?c=122&rota=top): F5 e link mantêm a escolha.
function readUrl() {
  const params = new URLSearchParams(window.location.search)
  const lane = params.get('rota')
  return {
    championId: Number(params.get('c')) || null,
    lane: LANES.some((l) => l.id === lane) ? (lane as Position) : null,
  }
}

export function App() {
  const champions = useApi<Champion[]>('/api/champions')
  const [initial] = useState(readUrl)
  const [championId, setChampionId] = useState<number | null>(initial.championId)
  const [lane, setLane] = useState<Position | null>(initial.lane)
  const [tab, setTab] = useState<Tab>('counters')

  const champion = useMemo(() => champions.data?.find((c) => c.id === championId) ?? null, [champions.data, championId])
  const position = champion ? (lane ?? mainLane(champion)) : lane

  useEffect(() => {
    const params = new URLSearchParams()
    if (champion) params.set('c', String(champion.id))
    if (position) params.set('rota', position)
    const query = params.toString()
    window.history.replaceState(null, '', query ? `?${query}` : window.location.pathname)
  }, [champion, position])

  const selectChampion = (next: Champion) => {
    setChampionId(next.id)
    // Mantém a rota escolhida se o campeão joga lá; senão, vai pra principal dele.
    setLane((current) => (current && next.lanes[current] >= 0.05 ? current : mainLane(next)))
  }

  return (
    <MotionConfig reducedMotion="user">
      <Background splash={champion?.splash} />
      <div className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6">
        <LayoutGroup>
          <motion.header
            layout
            transition={{ type: 'spring', stiffness: 160, damping: 24 }}
            className={champion ? 'pt-6 pb-6' : 'flex min-h-[78dvh] flex-col justify-center pt-10'}
          >
            <motion.div layout="position" className={champion ? 'mb-4 flex items-center gap-3' : 'mb-8 text-center'}>
              <motion.h1
                layout="position"
                className={
                  champion
                    ? 'bg-gradient-to-r from-violet-200 via-fuchsia-300 to-violet-400 bg-clip-text font-display text-2xl font-bold tracking-[0.2em] text-transparent'
                    : 'bg-gradient-to-r from-violet-200 via-fuchsia-300 to-violet-400 bg-clip-text font-display text-6xl font-bold tracking-[0.25em] text-transparent drop-shadow-[0_0_30px_rgb(192_132_252/0.45)] sm:text-7xl'
                }
              >
                ENZO
              </motion.h1>
              <AnimatePresence>
                {!champion && (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-3 text-violet-300/80"
                  >
                    Seu assistente de draft: counters, bans, build e runas em segundos.
                  </motion.p>
                )}
              </AnimatePresence>
              {champion && <span className="text-xs tracking-widest text-violet-400/70 uppercase">Draft</span>}
            </motion.div>

            <motion.div layout="position" className="mx-auto grid w-full max-w-3xl gap-3 lg:max-w-none lg:grid-cols-[1fr_auto]">
              <ChampionSearch
                champions={champions.data}
                loading={champions.loading}
                selected={champion}
                onSelect={selectChampion}
              />
              <LaneSelector value={position} champion={champion} onChange={setLane} />
            </motion.div>

            {champions.error && (
              <div className="mt-6">
                <ErrorState message={champions.error} onRetry={champions.retry} />
              </div>
            )}

            {!champion && !champions.error && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                className="mt-6 text-center text-xs text-violet-400/70"
              >
                <kbd className="rounded border border-violet-400/25 bg-void-800 px-1.5 font-display">/</kbd> buscar ·{' '}
                <kbd className="rounded border border-violet-400/25 bg-void-800 px-1.5 font-display">↑↓</kbd> escolher ·{' '}
                <kbd className="rounded border border-violet-400/25 bg-void-800 px-1.5 font-display">1–4</kbd> trocar de aba
              </motion.p>
            )}
          </motion.header>
        </LayoutGroup>

        <AnimatePresence mode="wait">
          {champion && position && (
            <motion.main
              key={`${champion.id}-${position}`}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            >
              <Analysis champion={champion} position={position} tab={tab} onTabChange={setTab} />
            </motion.main>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  )
}
