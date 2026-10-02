import { motion } from 'motion/react'
import { Skull, Swords, Trophy, User } from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { GameIcon } from '../../components/ui/GameIcon'
import { Skeleton } from '../../components/ui/Skeleton'
import { EmptyState } from '../../components/ui/States'
import { WinRateBar } from '../../components/ui/WinRateBar'
import type { CounterRow, CountersData } from '../../lib/api'
import { cn } from '../../lib/cn'
import { num, pct, winRateTone } from '../../lib/format'

const list = { hidden: {}, show: { transition: { staggerChildren: 0.035 } } }
const row = { hidden: { opacity: 0, x: -12 }, show: { opacity: 1, x: 0, transition: { type: 'spring' as const, stiffness: 260, damping: 26 } } }

export function CountersPanel({ data, championName }: { data: CountersData; championName: string }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="Te counteram"
        icon={<Skull className="size-4 text-rose-300" aria-hidden />}
        aside={<span className="text-xs text-violet-300/70">seu winrate contra</span>}
      >
        <CounterList rows={data.against} empty={`Nenhum campeão tem vantagem clara sobre ${championName} nessa rota.`} />
      </Card>
      <Card
        title="Você amassa"
        icon={<Trophy className="size-4 text-emerald-300" aria-hidden />}
        aside={<span className="text-xs text-violet-300/70">seu winrate contra</span>}
      >
        <CounterList rows={data.favorable} empty={`${championName} não tem confronto claramente favorável nessa rota.`} />
      </Card>
      <p className="text-xs text-violet-300/60 lg:col-span-2">
        Média do OP.GG e do Lolalytics ({data.tier.replace('_plus', '+').replace('_', ' ')}), só confrontos com 100+ partidas por fonte.
      </p>
    </div>
  )
}

function CounterList({ rows, empty }: { rows: CounterRow[]; empty: string }) {
  if (rows.length === 0) {
    return <EmptyState icon={<Swords className="size-6" strokeWidth={1.75} aria-hidden />} title="Sem dados suficientes">{empty}</EmptyState>
  }
  return (
    <motion.ol variants={list} initial="hidden" animate="show" className="-mx-2 space-y-0.5">
      {rows.map((counter, index) => (
        <motion.li
          key={counter.id}
          variants={row}
          className="group flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors duration-200 hover:bg-white/[0.04]"
        >
          <span className="w-5 text-right font-display text-xs text-violet-400/70 tabular-nums">{index + 1}</span>
          <GameIcon
            src={counter.icon}
            alt=""
            className="size-10 ring-1 ring-white/10 transition-transform duration-200 group-hover:scale-105 group-hover:ring-fuchsia-400/50"
          />
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-2 truncate font-medium text-violet-50">
              {counter.name}
              {counter.pool && (
                <span title={counter.pool} className="inline-flex items-center gap-1 rounded-md bg-fuchsia-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-fuchsia-200 ring-1 ring-fuchsia-400/30">
                  <User className="size-3" aria-hidden />
                  Você joga
                </span>
              )}
            </p>
            <p className="truncate text-xs text-violet-300/60 tabular-nums">
              {num(counter.games)} partidas
              <span className="hidden sm:inline">
                {counter.opgg && ` · OP.GG ${pct(counter.opgg.myWinRate)}`}
                {counter.lolalytics && ` · Lolalytics ${pct(counter.lolalytics.myWinRate)}`}
              </span>
            </p>
          </div>
          <WinRateBar rate={counter.myWinRate} className="hidden sm:block" />
          <span className={cn('w-16 text-right font-display text-lg font-semibold tabular-nums', winRateTone(counter.myWinRate))}>
            {pct(counter.myWinRate)}
          </span>
        </motion.li>
      ))}
    </motion.ol>
  )
}

export function CountersSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {[0, 1].map((card) => (
        <Card key={card}>
          <Skeleton className="mb-5 h-4 w-32" />
          <div className="space-y-3">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="size-10" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-28" />
                  <Skeleton className="h-3 w-40" />
                </div>
                <Skeleton className="h-5 w-14" />
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}
