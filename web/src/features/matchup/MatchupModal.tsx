import { motion } from 'motion/react'
import { Crosshair, Gem, Layers, Lightbulb, ScrollText, Shield, Swords, X, Zap, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Card } from '../../components/ui/Card'
import { GameIcon } from '../../components/ui/GameIcon'
import { Skeleton } from '../../components/ui/Skeleton'
import { ErrorState } from '../../components/ui/States'
import { matchupUrl, useApi, type Ability, type Champion, type CounterRow, type MatchupData, type MatchupTip, type Position, type Side } from '../../lib/api'
import { cn } from '../../lib/cn'
import { num, pct, winRateTone } from '../../lib/format'
import { laneLabel } from '../../lib/lanes'
import { BuildPanel, BuildSkeleton } from '../analysis/BuildPanel'
import { RunesPanel, RunesSkeleton } from '../analysis/RunesPanel'

type Tab = 'runes' | 'build' | 'play'

const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: 'runes', label: 'Runas', icon: Gem },
  { id: 'build', label: 'Build', icon: Layers },
  { id: 'play', label: 'Como jogar', icon: ScrollText },
]

const PLAY_STYLE: Record<NonNullable<MatchupData['guide']['playStyle']>, { label: string; tone: string; icon: LucideIcon }> = {
  aggressive: { label: 'Jogue agressivo', tone: 'text-emerald-200 bg-emerald-500/10 ring-emerald-400/30', icon: Swords },
  defensive: { label: 'Jogue na defensiva', tone: 'text-amber-200 bg-amber-500/10 ring-amber-400/30', icon: Shield },
  even: { label: 'Lane equilibrada', tone: 'text-violet-200 bg-violet-500/10 ring-violet-400/30', icon: Crosshair },
}

interface MatchupModalProps {
  champion: Champion
  enemy: CounterRow
  position: Position
  onClose: () => void
}

/** Confronto do campeão escolhido contra um counter: build e runas só desse duelo + como jogar. */
export function MatchupModal({ champion, enemy, position, onClose }: MatchupModalProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [tab, setTab] = useState<Tab>('runes')
  const url = matchupUrl(champion.id, enemy.id, position)
  const matchup = useApi<MatchupData>(url)
  const tip = useApi<MatchupTip>(matchup.data?.guide.hasTip ? `${url}/tip` : null)
  const champions = useApi<Champion[]>('/api/champions') // já carregada: só pra splash do adversário
  const splash = champions.data?.find((c) => c.id === enemy.id)?.splash

  useEffect(() => {
    const element = dialog.current
    const previous = document.activeElement as HTMLElement | null
    element?.showModal()
    const overflow = document.documentElement.style.overflow
    document.documentElement.style.overflow = 'hidden'
    return () => {
      document.documentElement.style.overflow = overflow
      element?.close()
      previous?.focus()
    }
  }, [])

  const lane = laneLabel(position)

  return (
    <dialog
      ref={dialog}
      aria-labelledby="matchup-title"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => event.target === event.currentTarget && onClose()}
      className={cn(
        'm-auto max-h-[94dvh] w-[min(72rem,calc(100vw-1rem))] overflow-hidden rounded-3xl border border-violet-400/20 bg-void-950 p-0 text-violet-50',
        'shadow-[0_30px_120px_-20px_rgb(0_0_0/0.9)] backdrop:bg-void-950/75 backdrop:backdrop-blur-sm',
      )}
    >
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 28 }}
        className="flex max-h-[94dvh] flex-col sm:h-[min(94dvh,52rem)]"
      >
        {/* Cabeçalho: quem contra quem, números e o plano de jogo. */}
        <header className="relative isolate shrink-0 overflow-hidden border-b border-white/5 px-4 pt-4 pb-4 sm:px-6 sm:pt-5">
          {splash && (
            <img src={splash} alt="" aria-hidden className="absolute inset-0 -z-10 h-full w-full object-cover object-[center_20%] opacity-30" />
          )}
          <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-r from-void-950 via-void-950/85 to-void-950/40" />

          <div className="flex items-start gap-3 sm:gap-4">
            <div className="flex shrink-0 items-center gap-2">
              <GameIcon src={champion.icon} alt="" className="size-12 ring-2 ring-violet-400/40 sm:size-14" />
              <span className="font-display text-xs font-bold text-fuchsia-300/80">VS</span>
              <GameIcon src={enemy.icon} alt="" className="size-12 ring-2 ring-rose-400/50 sm:size-14" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 id="matchup-title" className="truncate font-display text-xl font-bold sm:text-2xl">
                {champion.name} <span className="text-violet-400/70">vs</span> {enemy.name}
              </h2>
              <p className="mt-0.5 text-xs text-violet-300/80 tabular-nums sm:text-sm">
                {lane} · <span className={cn('font-semibold', winRateTone(enemy.myWinRate))}>{pct(enemy.myWinRate)} de vitória</span> ·{' '}
                {num(enemy.games)} partidas
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Fechar confronto"
              className="grid size-9 shrink-0 cursor-pointer place-items-center rounded-xl text-violet-300 ring-1 ring-white/10 transition-colors duration-200 hover:bg-white/10 hover:text-white focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>

          <GamePlan data={matchup.data} enemyName={enemy.name} />
          <TipBox loading={matchup.loading || tip.loading} hasTip={matchup.data?.guide.hasTip} tip={tip.data} />
        </header>

        <div role="tablist" aria-label="Confronto" className="grid shrink-0 grid-cols-3 gap-1 border-b border-white/5 bg-void-900/60 p-1.5">
          {TABS.map(({ id, label, icon: Icon }) => {
            const active = tab === id
            return (
              <button
                key={id}
                type="button"
                role="tab"
                id={`matchup-tab-${id}`}
                aria-selected={active}
                aria-controls="matchup-panel"
                onClick={() => setTab(id)}
                className={cn(
                  'relative flex cursor-pointer items-center justify-center gap-2 rounded-xl px-2 py-2 text-sm font-semibold',
                  'transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none',
                  active ? 'text-white' : 'text-violet-300/80 hover:bg-white/5 hover:text-violet-100',
                )}
              >
                {active && (
                  <motion.span
                    layoutId="matchup-tab-pill"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                    className="absolute inset-0 rounded-xl bg-gradient-to-br from-violet-600/90 to-fuchsia-600/80 ring-1 ring-fuchsia-300/30"
                  />
                )}
                <Icon className="relative size-4" aria-hidden />
                <span className="relative">{label}</span>
              </button>
            )
          })}
        </div>

        <div id="matchup-panel" role="tabpanel" aria-labelledby={`matchup-tab-${tab}`} aria-busy={matchup.loading} className="flex-1 overflow-y-auto p-3 sm:p-5">
          {matchup.error ? (
            <ErrorState message={matchup.error} onRetry={matchup.retry} />
          ) : !matchup.data ? (
            tab === 'runes' ? <RunesSkeleton /> : tab === 'build' ? <BuildSkeleton /> : <PlaySkeleton />
          ) : tab === 'runes' ? (
            <RunesPanel pages={matchup.data.build.runes} empty={`Poucas partidas de ${champion.name} contra ${enemy.name} pra montar runas.`} />
          ) : tab === 'build' ? (
            <BuildPanel build={matchup.data.build} />
          ) : (
            <HowToPlay data={matchup.data} enemyName={enemy.name} />
          )}
          {matchup.data && tab !== 'play' && (
            <p className="mt-3 text-xs text-violet-300/60 tabular-nums">
              Só partidas de {champion.name} contra {enemy.name} no OP.GG
              {matchup.data.guide.games > 0 && ` (${num(matchup.data.guide.games)} no confronto)`}.
            </p>
          )}
        </div>
      </motion.div>
    </dialog>
  )
}

function sideLabel(side: Side, enemyName: string, mine: string, theirs: string) {
  return side === 'me' ? mine : `${enemyName} ${theirs}`
}

function GamePlan({ data, enemyName }: { data?: MatchupData; enemyName: string }) {
  if (!data) {
    return (
      <div className="mt-4 flex gap-2">
        <Skeleton className="h-7 w-36 rounded-lg" />
        <Skeleton className="h-7 w-48 rounded-lg" />
      </div>
    )
  }
  const { playStyle, laneAdvantage, soloKillAdvantage } = data.guide
  const badges: { label: string; tone: string; icon: LucideIcon }[] = []
  if (playStyle) badges.push(PLAY_STYLE[playStyle])
  if (laneAdvantage) {
    badges.push({
      label: sideLabel(laneAdvantage, enemyName, 'Você leva vantagem na lane', 'leva vantagem na lane'),
      tone: laneAdvantage === 'me' ? PLAY_STYLE.aggressive.tone : 'text-rose-200 bg-rose-500/10 ring-rose-400/30',
      icon: Zap,
    })
  }
  if (soloKillAdvantage) {
    badges.push({
      label: sideLabel(soloKillAdvantage, enemyName, 'Você consegue mais abates solo', 'consegue mais abates solo'),
      tone: soloKillAdvantage === 'me' ? PLAY_STYLE.aggressive.tone : 'text-rose-200 bg-rose-500/10 ring-rose-400/30',
      icon: Swords,
    })
  }
  if (badges.length === 0) return null
  return (
    <ul className="mt-4 flex flex-wrap gap-2" aria-label="Plano de jogo">
      {badges.map(({ label, tone, icon: Icon }) => (
        <li key={label} className={cn('inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold ring-1', tone)}>
          <Icon className="size-3.5" aria-hidden />
          {label}
        </li>
      ))}
    </ul>
  )
}

function TipBox({ loading, hasTip, tip }: { loading: boolean; hasTip?: boolean; tip?: MatchupTip }) {
  if (!loading && (!hasTip || !tip?.text)) return null
  return (
    <div className="mt-3 flex gap-2.5 rounded-xl border border-fuchsia-400/20 bg-fuchsia-500/[0.07] px-3 py-2.5 text-sm text-violet-100">
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-fuchsia-300" aria-hidden />
      {tip?.text ? (
        <p>
          {tip.text}
          {!tip.translated && <span className="ml-1 text-xs text-violet-300/60">(original em inglês)</span>}
        </p>
      ) : (
        <div className="flex-1 space-y-1.5 py-0.5" aria-label="Carregando dica">
          <Skeleton className="h-3.5 w-full" />
          <Skeleton className="h-3.5 w-2/3" />
        </div>
      )}
    </div>
  )
}

function HowToPlay({ data, enemyName }: { data: MatchupData; enemyName: string }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <Card title={`O que ${enemyName} faz`} icon={<Zap className="size-4 text-rose-300" aria-hidden />}>
        <ul className="space-y-3">
          {data.enemy.abilities.map((ability) => (
            <AbilityRow key={ability.key} ability={ability} />
          ))}
        </ul>
      </Card>
      <div className="space-y-4">
        {data.enemy.tips.length > 0 && (
          <Card title={`Contra ${enemyName}`} icon={<Lightbulb className="size-4 text-fuchsia-300" aria-hidden />}>
            <ul className="space-y-2.5 text-sm text-violet-100/90">
              {data.enemy.tips.map((text) => (
                <li key={text} className="flex gap-2">
                  <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-fuchsia-400" />
                  {text}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-violet-300/60">Dicas oficiais da Riot.</p>
          </Card>
        )}
        <Card title="Seu winrate" icon={<Crosshair className="size-4 text-violet-300" aria-hidden />}>
          <Stat label="OP.GG (confronto)" value={data.guide.myWinRate} games={data.guide.games} />
        </Card>
      </div>
    </div>
  )
}

const ABILITY_TONE: Record<string, string> = {
  P: 'from-slate-400 to-slate-600',
  Q: 'from-violet-500 to-indigo-600',
  W: 'from-sky-400 to-cyan-600',
  E: 'from-fuchsia-500 to-pink-600',
  R: 'from-amber-300 to-orange-500',
}

function AbilityRow({ ability }: { ability: Ability }) {
  return (
    <li className="flex gap-3">
      <span className="relative shrink-0">
        <GameIcon src={ability.icon} alt="" className="size-11 rounded-xl ring-1 ring-white/15" />
        <span className={cn('absolute -right-1.5 -bottom-1.5 grid size-5 place-items-center rounded-md bg-gradient-to-br font-display text-[11px] font-bold text-white', ABILITY_TONE[ability.key])}>
          {ability.key}
        </span>
      </span>
      <div className="min-w-0">
        <p className="flex flex-wrap items-baseline gap-x-2 font-semibold text-violet-50">
          {ability.name}
          {ability.cooldown && (
            <span className="text-xs font-normal text-violet-300/70 tabular-nums">recarga {ability.cooldown.replaceAll('/', ' / ')}s</span>
          )}
        </p>
        <p className="mt-0.5 text-sm leading-relaxed text-violet-200/75">{ability.description}</p>
      </div>
    </li>
  )
}

function Stat({ label, value, games }: { label: string; value: number | null; games: number }): ReactNode {
  if (value === null) return <p className="text-sm text-violet-300/70">Sem partidas suficientes no OP.GG.</p>
  return (
    <p className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-violet-300/80">{label}</span>
      <span className="tabular-nums">
        <span className={cn('font-display text-lg font-semibold', winRateTone(value))}>{pct(value)}</span>
        <span className="ml-2 text-xs text-violet-300/60">{num(games)} partidas</span>
      </span>
    </p>
  )
}

function PlaySkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <Skeleton className="h-96 rounded-2xl" />
      <Skeleton className="h-56 rounded-2xl" />
    </div>
  )
}
