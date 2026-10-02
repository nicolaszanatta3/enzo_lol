import { AnimatePresence, motion } from 'motion/react'

/** Fundo da página: orbes roxos à deriva, grade e a splash do campeão escolhido. */
export function Background({ splash }: { splash?: string }) {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-void-950">
      <AnimatePresence>
        {splash && (
          <motion.img
            key={splash}
            src={splash}
            alt=""
            initial={{ opacity: 0, scale: 1.08 }}
            animate={{ opacity: 0.2, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
            className="absolute inset-0 h-full w-full object-cover object-top [mask-image:linear-gradient(to_bottom,black_10%,transparent_80%)]"
          />
        )}
      </AnimatePresence>

      <div className="absolute -top-40 -left-32 size-[42rem] rounded-full bg-violet-700/25 blur-3xl motion-safe:animate-drift-a" />
      <div className="absolute top-1/3 -right-40 size-[38rem] rounded-full bg-fuchsia-600/15 blur-3xl motion-safe:animate-drift-b" />
      <div className="absolute -bottom-48 left-1/4 size-[34rem] rounded-full bg-indigo-600/20 blur-3xl motion-safe:animate-drift-c" />

      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgb(167_139_250/0.06)_1px,transparent_1px),linear-gradient(to_bottom,rgb(167_139_250/0.06)_1px,transparent_1px)] bg-[size:56px_56px] [mask-image:radial-gradient(ellipse_at_top,black_20%,transparent_75%)]" />
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-fuchsia-500/70 to-transparent" />
    </div>
  )
}
