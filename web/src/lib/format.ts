const percent = new Intl.NumberFormat('pt-BR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const integer = new Intl.NumberFormat('pt-BR')

export const pct = (rate: number) => percent.format(rate)
export const num = (value: number) => integer.format(Math.round(value))

/** Cor do winrate do jogador: verde quando favorece, rosa quando atrapalha. */
export function winRateTone(rate: number) {
  if (rate >= 0.52) return 'text-emerald-300'
  if (rate <= 0.48) return 'text-rose-300'
  return 'text-violet-100'
}

/** Busca sem acento, caixa ou pontuação: "kai sa" acha "Kai'Sa". */
export const compact = (text: string) =>
  text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '')
