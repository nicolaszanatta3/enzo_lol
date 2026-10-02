import { Crosshair, HeartHandshake, Shield, Trees, Zap, type LucideIcon } from 'lucide-react'
import type { Champion, Position } from './api'

export const LANES: { id: Position; label: string; icon: LucideIcon }[] = [
  { id: 'top', label: 'Topo', icon: Shield },
  { id: 'jungle', label: 'Selva', icon: Trees },
  { id: 'mid', label: 'Meio', icon: Zap },
  { id: 'adc', label: 'Atirador', icon: Crosshair },
  { id: 'support', label: 'Suporte', icon: HeartHandshake },
]

export const laneLabel = (position: Position) => LANES.find((l) => l.id === position)?.label ?? position

/** Rota onde o campeão mais joga (ou topo, sem dados). */
export function mainLane(champion: Champion): Position {
  return LANES.reduce((best, lane) => (champion.lanes[lane.id] > champion.lanes[best] ? lane.id : best), 'top' as Position)
}
