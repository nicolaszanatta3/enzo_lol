import { useEffect, useState } from 'react'

export type Position = 'top' | 'jungle' | 'mid' | 'adc' | 'support'

export interface ChampionRef {
  id: number
  name: string
  icon: string | null
}

export interface Champion extends ChampionRef {
  splash: string
  aliases: string[]
  /** Fração das partidas do campeão em cada rota (OP.GG). */
  lanes: Record<Position, number>
}

export interface SourceStat {
  myWinRate: number
  games: number
}

export interface CounterRow extends ChampionRef {
  /** Winrate do campeão escolhido contra este (média OP.GG + Lolalytics). */
  myWinRate: number
  games: number
  opgg: SourceStat | null
  lolalytics: SourceStat | null
  /** Histórico do jogador com este campeão, se ele joga. */
  pool: string | null
}

export interface CountersData {
  against: CounterRow[]
  favorable: CounterRow[]
  tier: string
}

export interface BanRow extends ChampionRef {
  splash: string
  myWinRate: number
  pickRate: number
  threat: number
  games: number
}

export interface Stats {
  winRate: number
  games: number
  pickRate: number
}

export interface Item {
  id: number
  name: string
  icon: string | null
  gold: number
  description: string
}

export interface ItemSet extends Stats {
  items: Item[]
}

export interface Spell {
  id: number
  name: string
  icon: string | null
  description: string
}

export type AbilityKey = 'P' | 'Q' | 'W' | 'E' | 'R'

export interface Ability {
  key: AbilityKey
  name: string
  icon: string
}

export interface Rune {
  id: number
  name: string
  icon: string | null
  description: string
  selected: boolean
}

export interface RuneTree {
  tree: { id: number; key: string; name: string; icon: string }
  rows: Rune[][]
}

export interface BuildData {
  stats: {
    tier: number
    rank: number
    winRate: number
    pickRate: number
    banRate: number
    kda: number
    games: number
    lolalyticsTier: string | null
  }
  starter: ItemSet | null
  boots: ItemSet | null
  core: ItemSet | null
  situational: { slot: string; options: ItemSet[] }[]
  spells: (Stats & { spells: Spell[] }) | null
  skills: (Stats & { abilities: Ability[]; order: AbilityKey[]; priority: AbilityKey[] }) | null
  runes: (Stats & { primary: RuneTree | null; secondary: RuneTree | null; shards: Rune[][] }) | null
}

// Uma requisição por URL, compartilhada entre componentes; quem já chegou
// fica em `resolved` pra voltar a uma rota/aba sem piscar o carregamento.
const pending = new Map<string, Promise<unknown>>()
const resolved = new Map<string, unknown>()

function fetchJson<T>(url: string): Promise<T> {
  let request = pending.get(url)
  if (!request) {
    request = fetch(url)
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          throw new Error(typeof body?.detail === 'string' ? body.detail : `Erro ${response.status} no servidor.`)
        }
        const data = await response.json()
        resolved.set(url, data)
        return data
      })
      .catch((error: unknown) => {
        pending.delete(url)
        if (error instanceof TypeError) throw new Error('Sem conexão com o servidor do Enzo. Ele está rodando?')
        throw error
      })
    pending.set(url, request)
  }
  return request as Promise<T>
}

interface ApiState<T> {
  url: string | null
  data?: T
  error?: string
}

export function useApi<T>(url: string | null) {
  const [state, setState] = useState<ApiState<T>>({ url: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!url || resolved.has(url)) return
    let alive = true
    fetchJson<T>(url).then(
      (data) => alive && setState({ url, data }),
      (error: Error) => alive && setState({ url, error: error.message }),
    )
    return () => {
      alive = false
    }
  }, [url, attempt])

  const data = url ? ((resolved.get(url) as T | undefined) ?? (state.url === url ? state.data : undefined)) : undefined
  const error = !data && state.url === url ? state.error : undefined
  return {
    data,
    error,
    loading: Boolean(url) && !data && !error,
    retry: () => {
      setState({ url: null })
      setAttempt((n) => n + 1)
    },
  }
}
