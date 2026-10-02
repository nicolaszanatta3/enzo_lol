import { motion } from 'motion/react'
import { GameIcon } from '../../components/ui/GameIcon'
import { Skeleton } from '../../components/ui/Skeleton'
import type { BuildData, Champion, Position } from '../../lib/api'
import { cn } from '../../lib/cn'
import { num, pct, winRateTone } from '../../lib/format'
import { LANES } from '../../lib/lanes'

const OPGG_TIER_TONE: Record<number, string> = {
  1: 'from-amber-300 to-orange-500 text-void-950',
  2: 'from-fuchsia-400 to-violet-500 text-white',
  3: 'from-sky-400 to-indigo-500 text-white',
  4: 'from-slate-400 to-slate-600 text-white',
  5: 'from-stone-500 to-stone-700 text-white',
}

interface ChampionHeroProps {
  champion: Champion
  position: Position
  stats: BuildData['stats'] | undefined
}

export function ChampionHero({ champion, position, stats }: ChampionHeroProps) {
  const lane = LANES.find((l) => l.id === position)!
  const LaneIcon = lane.icon
  return (
    <motion.section
      key={champion.id}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="relative isolate overflow-hidden rounded-3xl border border-violet-400/20 bg-void-900 shadow-2xl shadow-violet-950/50"
    >
      <motion.img
        src={champion.splash}
        alt=""
        aria-hidden
        initial={{ scale: 1.12, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
        className="absolute inset-0 -z-10 h-full w-full object-cover object-[center_20%]"
      />
      <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-r from-void-950 via-void-950/85 to-void-950/20" />
      <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-t from-void-950/90 via-transparent to-transparent" />

      <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-end sm:p-7">
        <div className="relative shrink-0 self-start">
          <div aria-hidden className="absolute -inset-1.5 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 opacity-70 blur-md motion-safe:animate-glow" />
          <GameIcon src={champion.icon} alt={champion.name} className="relative size-20 ring-2 ring-fuchsia-300/70 sm:size-24" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-display text-xs font-semibold tracking-[0.2em] text-fuchsia-300 uppercase">
            <LaneIcon className="size-4" aria-hidden />
            {lane.label}
          </p>
          <h2 className="mt-1 font-display text-4xl leading-none font-bold tracking-tight text-white drop-shadow-[0_2px_12px_rgb(168_85_247/0.6)] sm:text-5xl">
            {champion.name}
          </h2>

          <dl className="mt-4 flex flex-wrap gap-2">
            {stats ? (
              <>
                {stats.tier > 0 && (
                  <div className={cn('rounded-lg bg-gradient-to-br px-2.5 py-1 font-display text-sm font-bold', OPGG_TIER_TONE[stats.tier])}>
                    <dt className="sr-only">Tier no OP.GG</dt>
                    <dd>OP.GG T{stats.tier}</dd>
                  </div>
                )}
                {stats.lolalyticsTier && <Stat label="Lolalytics" value={stats.lolalyticsTier} />}
                <Stat label="Vitórias" value={pct(stats.winRate)} tone={winRateTone(stats.winRate)} />
                <Stat label="Escolha" value={pct(stats.pickRate)} />
                <Stat label="Banimento" value={pct(stats.banRate)} />
                <Stat label="KDA" value={stats.kda.toFixed(2).replace('.', ',')} />
                <Stat label="Partidas" value={num(stats.games)} />
              </>
            ) : (
              Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-8 w-24" />)
            )}
          </dl>
        </div>
      </div>
    </motion.section>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-baseline gap-1.5 rounded-lg border border-white/10 bg-void-950/60 px-2.5 py-1 backdrop-blur-sm">
      <dt className="text-xs text-violet-300/70">{label}</dt>
      <dd className={cn('font-display text-sm font-semibold tabular-nums', tone ?? 'text-violet-50')}>{value}</dd>
    </div>
  )
}
