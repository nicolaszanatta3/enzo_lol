"""Cerebro do Enzo: recebe o comando ja transcrito e devolve o que falar.

Teste sem microfone (a partir da raiz do projeto):
    python -m src.core.enzo "to contra malfite, do que eu jogo?"
    python -m src.core.enzo --falar "to contra o darius"
    python -m src.core.enzo "quero jogar de fizz, o que devo banir?"
    python -m src.core.enzo "o que ta bom no top?"
    python -m src.core.enzo "meu time e naafiri, vlad, jinx e lulu, o que pego?"
"""

import sys
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from src.ai import router
from src.core import config
from src.lol import champions
from src.lol.advisor import CounterAdvisor, CounterPick, PoolChampion, best_from_pool, format_report
from src.lol.champions import Champion
from src.lol.draft import BanTarget, DraftAdvisor, PickResult, format_bans, format_meta, format_pick
from src.lol.meta import LaneEntry, MetaAdvisor
from src.lol.profiles import NEED_LABELS, ProfileStore
from src.lol.tips import TipTranslator

UNKNOWN_FALLBACK = ("Por enquanto eu manjo de counter, ban, meta da rota e pick pro seu time. "
                    "Pergunta uma dessas.")


@dataclass
class Reply:
    speech: str  # o que o Enzo fala
    console: str | None = None  # detalhes extras pro terminal
    # Algo pra falar DEPOIS da resposta principal, calculado enquanto ela toca.
    followup: Future | None = None


class Enzo:
    def __init__(self):
        self.advisor = CounterAdvisor()
        self.mcp = self.advisor.mcp
        self.meta = MetaAdvisor(self.mcp)
        self.draft = DraftAdvisor(self.advisor, self.meta, ProfileStore(self.mcp))
        self._background = ThreadPoolExecutor(max_workers=2)
        self.tips = TipTranslator()

    def warm_up_in_background(self) -> Future:
        """Carrega lista de campeoes e pool do jogador sem bloquear ninguem.
        Os perfis dos campeoes (classes e tipo de dano, ~2 min na primeira vez,
        depois ficam em disco) seguem carregando por fora, sem entrar no Future."""
        def warm_up():
            self.advisor.warm_up()
            self._background.submit(self._warm_up_profiles)
        return self._background.submit(warm_up)

    def _warm_up_profiles(self) -> None:
        try:
            self.draft.warm_up()
        except Exception as exc:  # so' adianta trabalho; o pick busca o que faltar
            print(f"[Enzo] Perfis dos campeoes nao pre-carregados: {exc}")

    def handle(self, command_text: str) -> Reply:
        # Pergunta clara nem passa pelo LLM: economiza cota (plano gratuito tem
        # ~20 pedidos/dia por modelo) e responde mais rapido. O LLM entra
        # quando a frase vem confusa ou pede mais contexto (pick com o time).
        local = router.route_locally(command_text)
        reply = self._answer_locally(local, command_text)
        if reply:
            return reply

        names = [c.name for c in champions.list_champions(self.mcp)]
        command = router.route(command_text, names)
        if command.action == router.ACTION_COUNTER:
            enemy = self._champion(command.enemy_champion)
            if enemy is None:
                return Reply("Não peguei contra qual campeão você tá. Fala o nome de novo.")
            return self._counter(enemy, command.position)
        if command.action == router.ACTION_BAN:
            mine = (champions.find_all_in_text(self.mcp, command_text)[:1] or [None])[0] \
                if command.find_in_whole_text else self._champion(command.my_champion)
            return self._ban(mine, command.position)
        if command.action == router.ACTION_META:
            return self._meta(command.position)
        if command.action == router.ACTION_PICK:
            return self._pick(command, command_text)
        return Reply(command.reply or UNKNOWN_FALLBACK)

    def _answer_locally(self, local: router.Command, command_text: str) -> Reply | None:
        """Responde sem LLM quando a frase e' inequivoca; None pra perguntar ao LLM."""
        found = champions.find_all_in_text(self.mcp, command_text)
        if local.action == router.ACTION_COUNTER and len(found) <= 1:
            # Mais campeoes na frase ("o vlad e' mid, to contra o darius") = pick com o time.
            enemy = champions.find_in_text(self.mcp, local.enemy_champion, fuzzy=False)
            if enemy:
                return self._counter(enemy, local.position)
        if local.action == router.ACTION_BAN:
            if len(found) == 1:
                return self._ban(found[0], local.position)
            if not found and local.position:
                return self._ban(None, local.position)
        if local.action == router.ACTION_META:
            return self._meta(local.position)
        return None

    def _champion(self, name: str | None) -> Champion | None:
        if not name:
            return None
        return champions.by_name(self.mcp, name) or champions.find_in_text(self.mcp, name)

    # --- Ban ---------------------------------------------------------------

    def _ban(self, mine: Champion | None, position: str | None) -> Reply:
        if mine is None:
            position = position or config.MAIN_POSITION
            targets = self.draft.bans_for_lane(position)
            if not targets:
                return Reply(f"Não consegui os dados do {position} agora. Tenta de novo daqui a pouco.")
            return Reply(
                speech=_lane_ban_speech(position, targets),
                console=format_bans(f"Bans pro {position} (mais fortes da rota)", targets),
            )

        position = position or self.draft.main_position(mine) or config.MAIN_POSITION
        targets = self.draft.bans_against(mine, position)
        console = format_bans(f"Bans pra jogar de {mine.name} no {position} (quem ganha dele)", targets)
        if targets:
            return Reply(_ban_speech(mine, position, targets), console)
        # Ninguem com vantagem e amostra: bane o mais forte da rota.
        lane_targets = self.draft.bans_for_lane(position)
        if not lane_targets:
            return Reply(f"Não achei dados de {mine.name} no {position}. Fala de novo o campeão e a rota.")
        return Reply(
            speech=(f"Ninguém ganha com folga do {mine.name} no {position}. "
                    f"Então bane o mais forte da rota: {lane_targets[0].champion.name}."),
            console=console + "\n" + format_bans(f"Bans pro {position} (mais fortes da rota)", lane_targets),
        )

    # --- Meta --------------------------------------------------------------

    def _meta(self, position: str | None) -> Reply:
        position = position or config.MAIN_POSITION
        entries = self.meta.ranking(position, config.META_MIN_PICK_RATE)
        if not entries:
            return Reply(f"Não consegui a tier list do {position} agora. Tenta de novo daqui a pouco.")
        pool_ids = {p.champion.id for p in self.advisor.player_pool()}
        return Reply(
            speech=_meta_speech(position, entries, pool_ids),
            console=format_meta(position, entries, pool_ids),
        )

    # --- Pick --------------------------------------------------------------

    def _pick(self, command: router.Command, command_text: str) -> Reply:
        unknown = []
        if command.find_in_whole_text:
            allies = [(c, None) for c in champions.find_all_in_text(self.mcp, command_text)]
            enemy = None
        else:
            allies = []
            for ally in command.allies:
                champion = self._champion(ally.champion)
                if champion:
                    allies.append((champion, ally.position))
                else:
                    unknown.append(ally.champion)
            enemy = self._champion(command.enemy_champion)
        if command.position:
            position = command.position
        elif allies:
            position = self.draft.my_position(allies)
        elif enemy:
            position = self.draft.enemy_position(enemy)
        else:
            position = config.MAIN_POSITION
        if not allies and not command.needs and not enemy:
            return self._meta(position)  # "o que eu pego no top?" sem contexto = meta

        result = self.draft.pick(position, allies, command.needs, enemy)
        off_role = [a for a in result.allies
                    if a.guessed and a.position != self.draft.main_position(a.champion)]
        speech = _pick_speech(result, off_role)
        if unknown:
            speech = f"Não reconheci {' e '.join(unknown)}. " + speech
        return Reply(speech, format_pick(result))

    def _counter(self, enemy: Champion, position: str | None) -> Reply:
        position = position or self.draft.enemy_position(enemy)
        picks = self.advisor.counters(enemy, position)
        if not picks:
            # Quase sempre e' nome mal transcrito ou rota dita errada.
            return Reply(f"Entendi {enemy.name}, mas quase ninguém joga de {enemy.name} no {position}. "
                         "Fala o nome de novo, devagar, pra eu ter certeza.")

        # Dica pro counter do pool se ele ganha o confronto; senao, pro melhor geral.
        mine = best_from_pool(picks)
        tip_for = mine if mine and mine.win_rate >= 0.5 else picks[0]
        return Reply(
            speech=_counter_speech(enemy, position, picks),
            console=format_report(enemy, position, picks),
            followup=self._background.submit(self._translated_tip, tip_for.champion, enemy, position),
        )

    def _translated_tip(self, mine: Champion, enemy: Champion, position: str) -> str | None:
        tip = self.advisor.matchup_tip(mine, enemy, position)
        translated = tip and self.tips.translate(mine, enemy, position, tip)
        # Dica em ingles nao ajuda falada; sem traducao, so' pula.
        return f"Dica de {mine.name}: {translated}" if translated else None


def _percent(rate: float) -> str:
    return f"{round(rate * 100)} por cento"


def _spoken_personal(pool: PoolChampion) -> str:
    if pool.games:
        return f"você tem {pool.wins} vitórias e {pool.games - pool.wins} derrotas na season"
    return f"você tem {round(pool.mastery_points / 1000)} mil pontos de maestria"


def _counter_speech(enemy: Champion, position: str, picks: list[CounterPick]) -> str:
    top = picks[:config.COUNTERS_SPOKEN]
    items = []
    for i, pick in enumerate(top):
        rate = _percent(pick.win_rate) if i == 0 else str(round(pick.win_rate * 100))
        items.append(f"{pick.champion.name} {rate}" + (", que você joga" if pick.pool else ""))
    listed = ", ".join(items[:-1]) + f" e {items[-1]}" if len(items) > 1 else items[0]
    speech = f"Contra {enemy.name} no {position}: {listed}."

    for pick in top:
        if pick.pool:
            speech += f" {pick.champion.name}: {_spoken_personal(pick.pool)}."

    mine = best_from_pool(picks)
    if mine is None:
        speech += " Ninguém do seu pool tem dados contra ele."
    elif mine not in top:
        rank = picks.index(mine) + 1
        if mine.win_rate >= 0.5:
            speech += (f" Do seu pool, o melhor é {mine.champion.name}, {rank}º da lista, "
                       f"com {_percent(mine.win_rate)}; {_spoken_personal(mine.pool)}.")
        else:
            speech += (f" Do seu pool ninguém vai bem: o melhor é {mine.champion.name}, "
                       f"com {_percent(mine.win_rate)}.")
    return speech


def _join(items: list[str]) -> str:
    return ", ".join(items[:-1]) + f" e {items[-1]}" if len(items) > 1 else items[0]


def _ban_speech(mine: Champion, position: str, targets: list[BanTarget]) -> str:
    first, others = targets[0], targets[1:config.BANS_SPOKEN]
    speech = (f"Pra jogar de {mine.name} no {position}, bane {first.champion.name}: "
              f"ganha {_percent(first.win_rate)} contra você e aparece em "
              f"{_percent(first.pick_rate)} das partidas.")
    if others:
        speech += f" Outras opções: {_join([t.champion.name for t in others])}."
    return speech


def _lane_ban_speech(position: str, targets: list[BanTarget]) -> str:
    first, others = targets[0], targets[1:config.BANS_SPOKEN]
    speech = (f"No {position}, o ban que mais vale é {first.champion.name}: "
              f"{_percent(first.win_rate)} de vitória em {_percent(first.pick_rate)} das partidas.")
    if others:
        speech += f" Depois, {_join([t.champion.name for t in others])}."
    return speech


def _meta_speech(position: str, entries: list[LaneEntry], pool_ids: set[int]) -> str:
    top = entries[:config.META_SPOKEN]
    speech = (f"No {position}, o que tá forte: {_join([e.champion.name for e in top])}. "
              f"{top[0].champion.name} lidera, com {_percent(top[0].win_rate)} de vitória.")
    if any(len(e.sources) < 2 for e in top):
        only_one = [e.champion.name for e in top if len(e.sources) < 2]
        speech += f" {_join(only_one)} só aparece em uma das fontes."
    in_pool = [(i, e) for i, e in enumerate(entries, 1) if e.champion.id in pool_ids]
    if in_pool:
        rank, entry = in_pool[0]
        if rank <= len(top):
            speech += f" {entry.champion.name} você já joga."
        else:
            speech += f" Do seu pool, o melhor é {entry.champion.name}, em {rank}º."
    return speech


def _pick_reason(option, result: PickResult) -> str:
    reasons = []
    if option.fills:
        reasons.append("dá " + " e ".join(NEED_LABELS[n] for n in option.fills))
    best_ally = max(option.synergy.items(), key=lambda kv: kv[1], default=None)
    if best_ally and best_ally[1] >= 0.01:
        reasons.append(f"combina com {best_ally[0]}")
    if option.versus is not None and option.versus >= 0.52:
        reasons.append(f"ganha do {result.enemy.name}")
    return f"{option.champion.name}, que {' e '.join(reasons)}" if reasons else option.champion.name


def _pick_speech(result: PickResult, off_role: list) -> str:
    """`off_role`: aliados cuja rota foi deduzida fora da principal deles
    (ex: Naafiri no jungle porque o mid ficou com o Vladimir); vale avisar."""
    context = []
    if result.allies:
        context.append("com " + _join([a.champion.name for a in result.allies]))
    if result.enemy:
        context.append(f"contra {result.enemy.name}")
    if result.required:
        context.append("precisando de " + _join([NEED_LABELS[n] for n in result.required]))
    speech = f"Pro {result.position}{' ' + ', '.join(context) if context else ''}. "

    if result.gaps:
        speech += f"Falta {_join([NEED_LABELS[n] for n in result.gaps])} no time. "
    if not result.options:
        wanted = _join([NEED_LABELS[n] for n in result.required]) if result.required else "nada"
        return speech + f"Não achei {wanted} com dados suficientes no {result.position}."

    top = result.options[:config.PICK_SPOKEN]
    speech += "Melhores: " + _join([_pick_reason(o, result) for o in top]) + "."
    mine = next(((i, o) for i, o in enumerate(result.options, 1) if o.pool), None)
    if mine and mine[1] in top:
        speech += f" {mine[1].champion.name} você já joga."
    elif mine:
        speech += f" Do seu pool, o melhor é {mine[1].champion.name}, em {mine[0]}º."
    if off_role:
        speech += " Considerei " + _join([f"{a.champion.name} no {a.position}" for a in off_role]) + "."
    return speech


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    speak = "--falar" in args
    text = " ".join(a for a in args if a != "--falar") or "to contra malphite, do que eu jogo?"

    enzo = Enzo()
    enzo.warm_up_in_background().result()
    reply = enzo.handle(text)
    if reply.console:
        print(reply.console)
    print(f"Enzo: {reply.speech}")
    tip = reply.followup.result() if reply.followup else None
    if tip:
        print(f"Enzo: {tip}")
    if speak:
        from src.voice import tts
        tts.speak(reply.speech)
        if tip:
            tts.speak(tip)
