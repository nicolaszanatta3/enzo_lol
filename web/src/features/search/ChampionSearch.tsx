import { AnimatePresence, motion } from 'motion/react'
import { LoaderCircle, Search, SearchX } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { GameIcon } from '../../components/ui/GameIcon'
import type { Champion } from '../../lib/api'
import { cn } from '../../lib/cn'
import { compact, pct } from '../../lib/format'
import { laneLabel, mainLane } from '../../lib/lanes'

const MAX_RESULTS = 8

interface ChampionSearchProps {
  champions: Champion[] | undefined
  loading: boolean
  selected: Champion | null
  onSelect: (champion: Champion) => void
}

/** Começo do nome primeiro, depois apelido ("mf"), depois qualquer trecho. */
function search(champions: Champion[], query: string): Champion[] {
  const q = compact(query)
  if (!q) return []
  const scored: [number, Champion][] = []
  for (const champion of champions) {
    const keys = champion.aliases.map(compact)
    const name = compact(champion.name)
    const score = name.startsWith(q) ? 0 : keys.some((k) => k.startsWith(q)) ? 1 : name.includes(q) ? 2 : -1
    if (score >= 0) scored.push([score, champion])
  }
  return scored.sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name)).slice(0, MAX_RESULTS).map(([, c]) => c)
}

export function ChampionSearch({ champions, loading, selected, onSelect }: ChampionSearchProps) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listId = useId()

  const results = useMemo(() => search(champions ?? [], query), [champions, query])

  // "/" em qualquer lugar foca a busca.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement
      if (event.key === '/' && !typing) {
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const choose = (champion: Champion) => {
    onSelect(champion)
    setQuery('')
    setOpen(false)
    inputRef.current?.blur()
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, results.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' && results[active]) {
      event.preventDefault()
      choose(results[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
      inputRef.current?.blur()
    }
  }

  const showList = open && query.trim().length > 0

  return (
    <div className="relative">
      <label htmlFor={`${listId}-input`} className="sr-only">
        Campeão
      </label>
      <div
        className={cn(
          'group flex items-center gap-3 rounded-2xl border border-violet-400/20 bg-void-900/80 px-4 py-3 shadow-lg shadow-black/30',
          'transition-[border-color,box-shadow] duration-200 ease-in-out',
          'focus-within:border-fuchsia-400/70 focus-within:shadow-[0_0_0_4px_rgb(217_70_239/0.15),0_10px_40px_-10px_rgb(168_85_247/0.5)]',
        )}
      >
        {selected ? (
          <GameIcon src={selected.icon} alt={selected.name} className="size-8 ring-1 ring-fuchsia-400/50" />
        ) : (
          <Search className="size-5 text-violet-400" aria-hidden />
        )}
        <input
          ref={inputRef}
          id={`${listId}-input`}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && results[active] ? `${listId}-${results[active].id}` : undefined}
          autoComplete="off"
          spellCheck={false}
          value={query}
          disabled={!champions}
          placeholder={selected ? `Trocar ${selected.name}…` : loading ? 'Carregando campeões…' : 'Qual campeão você vai jogar?'}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 bg-transparent text-base text-violet-50 placeholder:text-violet-300/50 focus:outline-none disabled:cursor-not-allowed sm:text-lg"
        />
        {loading ? (
          <LoaderCircle className="size-5 text-violet-400 motion-safe:animate-spin" aria-hidden />
        ) : (
          <kbd className="hidden rounded-md border border-violet-400/25 bg-void-800 px-2 py-0.5 font-display text-xs text-violet-300 sm:block">/</kbd>
        )}
      </div>

      <AnimatePresence>
        {showList && (
          <motion.ul
            id={listId}
            role="listbox"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.16, ease: 'easeOut' }}
            className="absolute inset-x-0 top-full z-50 mt-2 max-h-[22rem] overflow-y-auto rounded-2xl border border-white/10 bg-void-900/75 p-1.5 shadow-2xl shadow-black/60 backdrop-blur-md"
          >
            {results.length === 0 ? (
              <li className="flex items-center gap-3 px-3 py-4 text-sm text-violet-300/80">
                <SearchX className="size-4" aria-hidden />
                Nenhum campeão com “{query}”.
              </li>
            ) : (
              results.map((champion, index) => {
                const lane = mainLane(champion)
                return (
                  <li
                    key={champion.id}
                    id={`${listId}-${champion.id}`}
                    role="option"
                    aria-selected={index === active}
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => choose(champion)}
                    className={cn(
                      'relative flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 transition-colors duration-150',
                      index === active ? 'text-white' : 'text-violet-200',
                    )}
                  >
                    {index === active && (
                      <motion.span
                        layoutId="search-active"
                        transition={{ type: 'spring', stiffness: 500, damping: 38 }}
                        className="absolute inset-0 rounded-xl bg-gradient-to-r from-violet-600/40 to-fuchsia-600/20 ring-1 ring-fuchsia-400/30"
                      />
                    )}
                    <GameIcon src={champion.icon} alt="" className="relative size-9" />
                    <span className="relative flex-1 font-medium">{champion.name}</span>
                    {champion.lanes[lane] > 0 && (
                      <span className="relative text-xs text-violet-300/70 tabular-nums">
                        {laneLabel(lane)} · {pct(champion.lanes[lane])}
                      </span>
                    )}
                  </li>
                )
              })
            )}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}
