import { useState } from 'react'
import { cn } from '../../lib/cn'

/** Imagem do jogo (campeão, item, runa) com fallback se o CDN falhar. */
export function GameIcon({ src, alt, className, round }: { src: string | null; alt: string; className?: string; round?: boolean }) {
  const [broken, setBroken] = useState(false)
  if (!src || broken) {
    return (
      <span
        role="img"
        aria-label={alt}
        className={cn('grid place-items-center bg-void-700 font-display text-xs text-violet-300', round ? 'rounded-full' : 'rounded-lg', className)}
      >
        {alt.slice(0, 2)}
      </span>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      draggable={false}
      onError={() => setBroken(true)}
      className={cn('object-cover select-none', round ? 'rounded-full' : 'rounded-lg', className)}
    />
  )
}
