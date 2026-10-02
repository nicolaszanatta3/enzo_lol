import { motion } from 'motion/react'
import { Info, ShieldBan, ShieldCheck } from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { GameIcon } from '../../components/ui/GameIcon'
import { Skeleton } from '../../components/ui/Skeleton'
import { EmptyState } from '../../components/ui/States'
import type { BanRow } from '../../lib/api'
import { cn } from '../../lib/cn'
import { num, pct, winRateTone } from '../../lib/format'

const FEATURED = 3

export function BansPanel({ bans, championName }: { bans: BanRow[]; championName: string }) {
  if (bans.length === 0) {
    return (
      <Card>
        <EmptyState icon={<ShieldCheck className="size-6" strokeWidth={1.75} aria-hidden />} title="Nada urgente pra banir">
          Nenhum campeão jogado com frequência tem vantagem sobre {championName} nessa rota. Bane o que mais te incomoda.
        </EmptyState>
      </Card>
    )
  }
  const maxThreat = bans[0].threat
  const rest = bans.slice(FEATURED)

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        {bans.slice(0, FEATURED).map((ban, index) => (
          <motion.article
            key={ban.id}
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 22, delay: index * 0.08 }}
            whileHover={{ y: -4 }}
            className={cn(
              'group relative isolate flex min-h-64 flex-col justify-end overflow-hidden rounded-2xl border p-4',
              index === 0
                ? 'border-fuchsia-400/60 shadow-[0_0_40px_-8px_rgb(217_70_239/0.55)]'
                : 'border-violet-400/20 shadow-xl shadow-black/40',
            )}
          >
            <img
              src={ban.splash}
              alt=""
              aria-hidden
              loading="lazy"
              className="absolute inset-0 -z-10 h-full w-full object-cover object-[center_25%] transition-transform duration-700 ease-out group-hover:scale-110"
            />
            <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-t from-void-950 via-void-950/75 to-void-950/10" />

            <span
              className={cn(
                'absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-lg px-2 py-1 font-display text-xs font-bold tracking-wider uppercase',
                index === 0 ? 'bg-gradient-to-r from-fuchsia-500 to-violet-600 text-white' : 'bg-void-950/70 text-violet-200 ring-1 ring-white/10',
              )}
            >
              <ShieldBan className="size-3.5" aria-hidden />
              {index === 0 ? 'Ban prioritário' : `#${index + 1}`}
            </span>

            <h4 className="font-display text-2xl font-bold text-white">{ban.name}</h4>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-violet-300/70">Seu winrate contra</dt>
                <dd className={cn('font-display text-lg font-semibold tabular-nums', winRateTone(ban.myWinRate))}>{pct(ban.myWinRate)}</dd>
              </div>
              <div>
                <dt className="text-violet-300/70">Aparece em</dt>
                <dd className="font-display text-lg font-semibold text-violet-50 tabular-nums">{pct(ban.pickRate)}</dd>
              </div>
            </dl>
            <ThreatMeter value={ban.threat / maxThreat} className="mt-3" />
          </motion.article>
        ))}
      </div>

      {rest.length > 0 && (
        <Card title="Outras opções" icon={<ShieldBan className="size-4 text-violet-300" aria-hidden />}>
          <ol className="-mx-2 grid gap-0.5 sm:grid-cols-2">
            {rest.map((ban, index) => (
              <motion.li
                key={ban.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.25 + index * 0.05 }}
                className="flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors duration-200 hover:bg-white/[0.04]"
              >
                <span className="w-5 text-right font-display text-xs text-violet-400/70 tabular-nums">{index + FEATURED + 1}</span>
                <GameIcon src={ban.icon} alt="" className="size-10 ring-1 ring-white/10" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{ban.name}</p>
                  <p className="text-xs text-violet-300/60 tabular-nums">
                    aparece em {pct(ban.pickRate)} · {num(ban.games)} partidas
                  </p>
                </div>
                <span className={cn('font-display text-lg font-semibold tabular-nums', winRateTone(ban.myWinRate))}>{pct(ban.myWinRate)}</span>
              </motion.li>
            ))}
          </ol>
        </Card>
      )}

      <p className="flex items-start gap-2 text-xs text-violet-300/60">
        <Info className="mt-px size-3.5 shrink-0" aria-hidden />
        Ameaça = quanto aparece na rota × quanto ganha de {championName}. Um counter fortíssimo que ninguém joga não vale o ban.
      </p>
    </div>
  )
}

function ThreatMeter({ value, className }: { value: number; className?: string }) {
  return (
    <div className={className}>
      <div className="mb-1 flex justify-between text-[10px] font-semibold tracking-widest text-violet-300/70 uppercase">
        <span>Ameaça</span>
        <span className="tabular-nums">{Math.round(value * 100)}</span>
      </div>
      <div aria-hidden className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(value, 0.04) * 100}%` }}
          transition={{ type: 'spring', stiffness: 90, damping: 18, delay: 0.3 }}
          className="h-full rounded-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-rose-400"
        />
      </div>
    </div>
  )
}

export function BansSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-64 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-40 rounded-2xl" />
    </div>
  )
}
