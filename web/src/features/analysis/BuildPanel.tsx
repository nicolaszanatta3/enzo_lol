import { motion } from 'motion/react'
import { ChevronRight, ChevronsUp, Footprints, Layers, Sparkles, Sword, WandSparkles } from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { GameIcon } from '../../components/ui/GameIcon'
import { Skeleton } from '../../components/ui/Skeleton'
import { Tooltip } from '../../components/ui/Tooltip'
import type { AbilityKey, BuildOptions, Item, ItemSet, Skills, Spell, Stats } from '../../lib/api'
import { cn } from '../../lib/cn'
import { num, pct, winRateTone } from '../../lib/format'

const SKILL_TONE: Record<AbilityKey, string> = {
  P: 'from-slate-400 to-slate-600',
  Q: 'from-violet-500 to-indigo-600',
  W: 'from-sky-400 to-cyan-600',
  E: 'from-fuchsia-500 to-pink-600',
  R: 'from-amber-300 to-orange-500',
}

export function BuildPanel({ build }: { build: BuildOptions }) {
  const path: { label: string; options: ItemSet[]; icon: React.ReactNode; size: keyof typeof TILE_SIZE }[] = []
  if (build.starter.length) path.push({ label: 'Inicial', options: build.starter, icon: <Sword className="size-3.5" aria-hidden />, size: 'md' })
  if (build.boots.length) path.push({ label: 'Botas', options: build.boots, icon: <Footprints className="size-3.5" aria-hidden />, size: 'md' })
  if (build.core.length) path.push({ label: 'Core', options: build.core, icon: <Layers className="size-3.5" aria-hidden />, size: 'lg' })
  const [spells, ...otherSpells] = build.spells

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card title="Caminho principal" icon={<Layers className="size-4 text-fuchsia-300" aria-hidden />} className="xl:col-span-2">
        <div className="flex flex-wrap items-start gap-x-2 gap-y-5">
          {path.map(({ label, options: [main, ...alternatives], icon, size }, index) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, type: 'spring', stiffness: 220, damping: 24 }}
              className="flex items-start gap-2"
            >
              {index > 0 && <ChevronRight className="mt-6 size-5 shrink-0 text-violet-500/70" aria-hidden />}
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-widest text-violet-300/70 uppercase">
                  {icon}
                  {label}
                </p>
                <div className="flex gap-1.5">
                  {main.items.map((item, i) => (
                    <ItemTile key={`${item.id}-${i}`} item={item} size={size} />
                  ))}
                </div>
                <SetStats stats={main} />
                <Alternatives options={alternatives} />
              </div>
            </motion.div>
          ))}
        </div>
      </Card>

      {spells && (
        <Card title="Feitiços" icon={<WandSparkles className="size-4 text-fuchsia-300" aria-hidden />}>
          <div className="flex gap-2">
            {spells.spells.map((spell) => (
              <SpellTile key={spell.id} spell={spell} className="size-14 rounded-xl" />
            ))}
          </div>
          <SetStats stats={spells} />
          {otherSpells.length > 0 && (
            <ul className="mt-3 space-y-1.5 border-t border-white/5 pt-3" aria-label="Outras opções de feitiços">
              {otherSpells.map((option) => (
                <li key={option.spells.map((s) => s.id).join('-')} className="flex items-center gap-2">
                  <span className="w-5 text-[11px] text-violet-400/70">ou</span>
                  {option.spells.map((spell) => (
                    <SpellTile key={spell.id} spell={spell} className="size-8 rounded-lg" />
                  ))}
                  <OptionStats stats={option} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {build.situational.length > 0 && (
        <Card title="Item a item" icon={<Sparkles className="size-4 text-fuchsia-300" aria-hidden />} className="xl:col-span-3">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {build.situational.map(({ slot, options }) => (
              <div key={slot}>
                <p className="mb-2 text-[11px] font-semibold tracking-widest text-violet-300/70 uppercase">{slot}</p>
                <ul className="space-y-1.5">
                  {options.map((option) => (
                    <li key={option.items.map((i) => i.id).join('-')} className="flex items-center gap-3 rounded-xl bg-white/[0.03] p-1.5 pr-3 ring-1 ring-white/5">
                      {option.items.map((item) => (
                        <ItemTile key={item.id} item={item} size="sm" />
                      ))}
                      <span className="min-w-0 flex-1 truncate text-sm text-violet-100">{option.items[0]?.name}</span>
                      <span className={cn('font-display text-sm font-semibold tabular-nums', winRateTone(option.winRate))}>{pct(option.winRate)}</span>
                      <span className="w-12 text-right text-xs text-violet-300/60 tabular-nums">{pct(option.pickRate)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-violet-300/60">Vitória e frequência de cada opção naquele slot.</p>
        </Card>
      )}

      {build.skills && (
        <Card title="Habilidades" icon={<ChevronsUp className="size-4 text-fuchsia-300" aria-hidden />} className="xl:col-span-3">
          <SkillOrder skills={build.skills} />
        </Card>
      )}
    </div>
  )
}

/** Outras opções pra mesma etapa, menores, embaixo da principal. */
function Alternatives({ options }: { options: ItemSet[] }) {
  if (options.length === 0) return null
  return (
    <ul className="mt-3 space-y-1.5 border-t border-white/5 pt-2.5" aria-label="Outras opções">
      {options.map((option) => (
        <li key={option.items.map((i) => i.id).join('-')} className="flex items-center gap-1.5">
          <span className="w-5 text-[11px] text-violet-400/70">ou</span>
          {option.items.map((item, i) => (
            <ItemTile key={`${item.id}-${i}`} item={item} size="xs" />
          ))}
          <OptionStats stats={option} />
        </li>
      ))}
    </ul>
  )
}

function OptionStats({ stats }: { stats: Stats }) {
  return (
    <span className="ml-1.5 text-[11px] whitespace-nowrap tabular-nums" title={`${num(stats.games)} partidas`}>
      <span className={cn('font-semibold', winRateTone(stats.winRate))}>{pct(stats.winRate)}</span>
      <span className="text-violet-300/60"> · {pct(stats.pickRate)}</span>
    </span>
  )
}

function SpellTile({ spell, className }: { spell: Spell; className: string }) {
  return (
    <Tooltip
      content={
        <>
          <p className="font-semibold text-white">{spell.name}</p>
          <p className="mt-1 line-clamp-5 text-violet-200/80">{spell.description}</p>
        </>
      }
    >
      <span
        tabIndex={0}
        aria-label={spell.name}
        className="block rounded-xl ring-1 ring-violet-400/30 transition duration-200 hover:-translate-y-0.5 hover:ring-fuchsia-400 focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none"
      >
        <GameIcon src={spell.icon} alt={spell.name} className={className} />
      </span>
    </Tooltip>
  )
}

function SkillOrder({ skills }: { skills: Skills }) {
  const ability = (key: AbilityKey) => skills.abilities.find((a) => a.key === key)
  const rows: AbilityKey[] = ['Q', 'W', 'E', 'R']
  return (
    <div className="space-y-5">
      {skills.priority.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-xs text-violet-300/70">Maximize</span>
          {skills.priority.map((key, index) => {
            const a = ability(key)
            return (
              <motion.span
                key={key}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: index * 0.1, type: 'spring', stiffness: 300, damping: 20 }}
                className="flex items-center gap-2"
              >
                {index > 0 && <ChevronRight className="size-4 text-violet-500" aria-hidden />}
                <span className="relative">
                  {a && <GameIcon src={a.icon} alt={a.name} className="size-11 rounded-xl ring-1 ring-white/15" />}
                  <span className={cn('absolute -right-1.5 -bottom-1.5 grid size-5 place-items-center rounded-md bg-gradient-to-br font-display text-[11px] font-bold text-white', SKILL_TONE[key])}>
                    {key}
                  </span>
                </span>
              </motion.span>
            )
          })}
          <SetStats stats={skills} className="mt-0 ml-auto" />
        </div>
      )}

      {skills.order.length > 0 && (
        <div className="overflow-x-auto pb-1">
          <table className="border-separate border-spacing-1">
            <caption className="sr-only">Ordem de habilidades por nível</caption>
            <tbody>
              {rows.map((key) => {
                const a = ability(key)
                return (
                  <tr key={key}>
                    <th scope="row" className="pr-2">
                      <span className="flex items-center gap-2">
                        {a && <GameIcon src={a.icon} alt="" className="size-8 rounded-md" />}
                        <span className="w-24 truncate text-left text-xs font-medium text-violet-200" title={a?.name}>
                          {a?.name ?? key}
                        </span>
                      </span>
                    </th>
                    {skills.order.map((levelKey, level) => (
                      <td key={level} className="p-0">
                        {levelKey === key ? (
                          <motion.span
                            initial={{ opacity: 0, scale: 0.4 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: 0.15 + level * 0.03, type: 'spring', stiffness: 400, damping: 22 }}
                            className={cn('grid size-8 place-items-center rounded-md bg-gradient-to-br font-display text-xs font-bold text-white shadow-md shadow-black/40', SKILL_TONE[key])}
                          >
                            {level + 1}
                          </motion.span>
                        ) : (
                          <span aria-hidden className="block size-8 rounded-md bg-white/[0.04] ring-1 ring-white/5" />
                        )}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const TILE_SIZE = { xs: 'size-7', sm: 'size-9', md: 'size-12', lg: 'size-14' }

function ItemTile({ item, size }: { item: Item; size: keyof typeof TILE_SIZE }) {
  return (
    <Tooltip
      content={
        <>
          <p className="font-semibold text-white">{item.name}</p>
          {item.gold > 0 && <p className="text-amber-300 tabular-nums">{num(item.gold)} de ouro</p>}
          {item.description && <p className="mt-1 line-clamp-6 whitespace-pre-line text-violet-200/80">{item.description}</p>}
        </>
      }
    >
      <span
        tabIndex={0}
        aria-label={item.name}
        className="block rounded-lg ring-1 ring-violet-400/30 transition duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-fuchsia-500/25 hover:ring-fuchsia-400 focus-visible:ring-2 focus-visible:ring-fuchsia-400 focus-visible:outline-none"
      >
        <GameIcon src={item.icon} alt={item.name} className={TILE_SIZE[size]} />
      </span>
    </Tooltip>
  )
}

function SetStats({ stats, className }: { stats: Stats; className?: string }) {
  return (
    <p className={cn('mt-2 flex gap-2 text-xs tabular-nums', className)}>
      <span className={cn('font-semibold', winRateTone(stats.winRate))}>{pct(stats.winRate)} vitórias</span>
      <span className="text-violet-300/60">{num(stats.games)} partidas</span>
    </p>
  )
}

export function BuildSkeleton() {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Skeleton className="h-44 rounded-2xl xl:col-span-2" />
      <Skeleton className="h-44 rounded-2xl" />
      <Skeleton className="h-52 rounded-2xl xl:col-span-3" />
    </div>
  )
}
