import { motion } from 'motion/react'
import { Gem } from 'lucide-react'
import { useState } from 'react'
import { Card } from '../../components/ui/Card'
import { GameIcon } from '../../components/ui/GameIcon'
import { Skeleton } from '../../components/ui/Skeleton'
import { EmptyState } from '../../components/ui/States'
import { Tooltip } from '../../components/ui/Tooltip'
import type { Rune, RunePage, RuneTree } from '../../lib/api'
import { cn } from '../../lib/cn'
import { num, pct, winRateTone } from '../../lib/format'

// Cor de cada árvore, como no cliente do jogo.
const TREE_COLOR: Record<string, string> = {
  Precision: '#e6c171',
  Domination: '#ef5a5f',
  Sorcery: '#8f9dff',
  Resolve: '#8fd16a',
  Inspiration: '#4fc3d4',
}
const SHARD_COLOR = '#c4b5fd'
const SHARD_ROWS = ['Ataque', 'Flex', 'Defesa']

const treeColor = (tree: RuneTree | null) => (tree && TREE_COLOR[tree.tree.key]) ?? SHARD_COLOR
const keystoneOf = (page: RunePage) => page.primary?.rows[0]?.find((rune) => rune.selected)

export function RunesPanel({ pages, empty = 'O OP.GG ainda não tem runas com amostra suficiente pra essa rota.' }: {
  pages: RunePage[]
  empty?: string
}) {
  const [selected, setSelected] = useState(0)
  const page = pages[selected] ?? pages[0]
  if (!page?.primary) {
    return (
      <Card>
        <EmptyState icon={<Gem className="size-6" strokeWidth={1.75} aria-hidden />} title="Sem página de runas">
          {empty}
        </EmptyState>
      </Card>
    )
  }
  return (
    <div className="space-y-3">
      {pages.length > 1 && <PagePicker pages={pages} selected={selected} onSelect={setSelected} />}
      <div key={selected} className="grid gap-4 lg:grid-cols-[1.25fr_1fr_0.8fr]">
        <TreeCard tree={page.primary} label="Principal" keystone delay={0} />
        {page.secondary && <TreeCard tree={page.secondary} label="Secundária" delay={0.12} />}
        <Card title="Fragmentos" icon={<Gem className="size-4 text-violet-300" aria-hidden />}>
          <div className="space-y-4">
            {page.shards.map((row, index) => (
              <div key={index}>
                <p className="mb-2 text-[11px] font-semibold tracking-widest text-violet-300/60 uppercase">{SHARD_ROWS[index]}</p>
                <div className="flex gap-3">
                  {row.map((rune, i) => (
                    <RuneIcon key={`${rune.id}-${i}`} rune={rune} color={SHARD_COLOR} size="sm" delay={0.3 + index * 0.08} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <p className="text-xs text-violet-300/60 tabular-nums">
        <span className={cn('font-semibold', winRateTone(page.winRate))}>{pct(page.winRate)} vitórias</span> em {num(page.games)} partidas
        ({pct(page.pickRate)} dos jogadores){page.label && ` · ${page.label}`}.
      </p>
    </div>
  )
}

function PagePicker({ pages, selected, onSelect }: { pages: RunePage[]; selected: number; onSelect: (index: number) => void }) {
  return (
    <div role="group" aria-label="Páginas de runas" className="grid gap-2 sm:grid-cols-3">
      {pages.map((page, index) => {
        const keystone = keystoneOf(page)
        const color = treeColor(page.primary)
        const active = index === selected
        return (
          <button
            key={index}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(index)}
            className={cn(
              'relative flex items-center gap-3 rounded-2xl border bg-void-900/85 p-2.5 pr-3 text-left',
              'transition duration-200 ease-out focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none',
              active ? 'border-transparent' : 'border-violet-400/15 hover:border-violet-400/35 hover:bg-void-800/90',
            )}
            style={active ? { boxShadow: `inset 0 0 0 1.5px ${color}, 0 0 28px -10px ${color}` } : undefined}
          >
            <span className="relative shrink-0">
              <GameIcon src={keystone?.icon ?? null} alt="" round className={cn('size-10 transition', !active && 'opacity-70')} />
              {page.secondary && (
                <GameIcon
                  src={page.secondary.tree.icon}
                  alt=""
                  className="absolute -right-1 -bottom-1 size-5 rounded-full bg-void-950 p-0.5 ring-1 ring-white/10"
                />
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold" style={{ color: active ? color : undefined }}>
                {keystone?.name ?? page.primary?.tree.name}
              </span>
              <span className="block truncate text-[11px] text-violet-300/70">
                {page.label || `${page.primary?.tree.name} + ${page.secondary?.tree.name}`}
              </span>
            </span>
            <span className="text-right text-xs tabular-nums">
              <span className={cn('block font-display font-semibold', winRateTone(page.winRate))}>{pct(page.winRate)}</span>
              <span className="block text-violet-300/60">{pct(page.pickRate)}</span>
            </span>
          </button>
        )
      })}
    </div>
  )
}

function TreeCard({ tree, label, keystone, delay }: { tree: RuneTree; label: string; keystone?: boolean; delay: number }) {
  const color = treeColor(tree)
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: 'spring', stiffness: 200, damping: 24 }}
    >
      <Card className="h-full">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-2xl opacity-60"
          style={{ background: `radial-gradient(ellipse at top, ${color}22, transparent 60%)` }}
        />
        <header className="relative mb-5 flex items-center gap-3">
          <GameIcon src={tree.tree.icon} alt="" className="size-9 rounded-none bg-transparent" />
          <div>
            <p className="text-[11px] font-semibold tracking-widest text-violet-300/60 uppercase">{label}</p>
            <h3 className="font-display text-lg font-bold" style={{ color }}>
              {tree.tree.name}
            </h3>
          </div>
        </header>
        <div className="relative space-y-4">
          {tree.rows.map((row, index) => {
            const big = keystone && index === 0
            return (
              <div key={index} className={cn('flex justify-around gap-2', big && 'border-b border-white/5 pb-4')}>
                {row.map((rune) => (
                  <RuneIcon key={rune.id} rune={rune} color={color} size={big ? 'lg' : 'md'} delay={delay + 0.1 + index * 0.08} />
                ))}
              </div>
            )
          })}
        </div>
      </Card>
    </motion.div>
  )
}

const RUNE_SIZE = { sm: 'size-8', md: 'size-10', lg: 'size-14' }

function RuneIcon({ rune, color, size, delay }: { rune: Rune; color: string; size: keyof typeof RUNE_SIZE; delay: number }) {
  return (
    <Tooltip
      content={
        <>
          <p className="font-semibold" style={{ color }}>
            {rune.name}
          </p>
          {rune.description && <p className="mt-1 line-clamp-5 text-violet-200/80">{rune.description}</p>}
        </>
      }
    >
      <motion.span
        tabIndex={0}
        aria-label={`${rune.name}${rune.selected ? ' (escolhida)' : ''}`}
        initial={rune.selected ? { scale: 0.5, opacity: 0 } : false}
        animate={rune.selected ? { scale: 1, opacity: 1 } : undefined}
        transition={{ delay, type: 'spring', stiffness: 380, damping: 18 }}
        className={cn(
          'block rounded-full transition duration-200 focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none',
          rune.selected ? 'bg-void-950 p-0.5' : 'opacity-30 grayscale hover:opacity-70 hover:grayscale-0',
        )}
        style={rune.selected ? { boxShadow: `0 0 0 2px ${color}, 0 0 22px -2px ${color}` } : undefined}
      >
        <GameIcon src={rune.icon} alt={rune.name} round className={RUNE_SIZE[size]} />
      </motion.span>
    </Tooltip>
  )
}

export function RunesSkeleton() {
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 rounded-2xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.25fr_1fr_0.8fr]">
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    </div>
  )
}
