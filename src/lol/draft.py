"""Fase de escolha: quem banir e quem pegar pra completar o time.

Ban (quero jogar de X):
    Os counters de X na rota (OP.GG + Lolalytics, via CounterAdvisor) pesados
    pela chance de aparecerem: ameaca = pick rate x (winrate dele contra X - 50%).
    Um counter fortissimo que ninguem joga nao vale o ban.
Ban (sem campeao, so' a rota):
    Os mais fortes da rota, pela mesma formula com o winrate geral.

Pick (meu time e' A, B, C...; estou no top; preciso de carry...):
    Candidatos = campeoes jogados na rota + o pool do jogador. Nota de cada um,
    em pontos de winrate somados:
      - forca na rota (winrate medio das fontes - 50%);
      - sinergia com cada aliado (Lolalytics: delta normalizado da dupla nos
        ultimos 30 dias; OP.GG: winrate da dupla - o esperado pelos dois;
        cada um encolhido pela amostra, depois media das fontes);
      - confronto contra o adversario de rota, se citado;
      - bonus por suprir o que falta na composicao (sem frontline, so' dano
        fisico...), detectado pelos perfis dos aliados.
    Necessidade DITA pelo jogador ("meu time nao tem carry") vira filtro.
    A rota de cada aliado, se nao for dita, e' a combinacao mais provavel
    pelo role_rate do OP.GG.
"""

import itertools
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from src.core import config
from src.lol import lolalytics
from src.lol.advisor import CounterAdvisor, CounterPick, PoolChampion, personal_summary
from src.lol.champions import Champion
from src.lol.meta import POSITIONS, LaneEntry, MetaAdvisor, tier_label
from src.lol.opgg_mcp import McpError
from src.lol.profiles import NEED_AD, NEED_AP, NEED_CARRY, NEED_LABELS, NEED_TANK, Profile, ProfileStore

# Sinergia real entre dois campeoes raramente passa de ~1-2 pontos de winrate,
# mas com poucas partidas o acaso gera +-5. Cada delta e' encolhido por
# n / (n + SYNERGY_PRIOR_GAMES): com 2.500 partidas vale metade, com 25 mil ~90%.
# (2.500 = variancia de um jogo (0,25) / variancia tipica da sinergia (0,01^2).)
SYNERGY_PRIOR_GAMES = 2500
MIN_SYNERGY_GAMES = 30  # abaixo disso nem entra (o encolhimento ja' zeraria)
ROLE_RATE_FLOOR = 0.01  # rota nunca jogada ainda e' possivel, so' improvavel
# Adversario que joga pelo menos isso na rota do jogador e' enfrentado la'
# (Yone: ~50% top); abaixo, vale a rota principal dele (Leona: ~0% top).
MAIN_LANE_MIN_ROLE_RATE = 0.2


# --- Ban -------------------------------------------------------------------

@dataclass
class BanTarget:
    champion: Champion
    win_rate: float  # contra o campeao do jogador (ou geral, no ban por rota)
    pick_rate: float
    counter: CounterPick | None = None  # numeros por fonte, no ban contra um campeao

    @property
    def threat(self) -> float:
        return self.pick_rate * (self.win_rate - 0.5)


# --- Pick ------------------------------------------------------------------

@dataclass
class Ally:
    champion: Champion
    position: str
    guessed: bool  # rota deduzida, nao dita
    profile: Profile | None = None


@dataclass
class PickOption:
    entry: LaneEntry
    profile: Profile | None
    synergy: dict[str, float] = field(default_factory=dict)  # nome do aliado -> delta
    versus: float | None = None  # winrate contra o adversario de rota
    fills: list[str] = field(default_factory=list)  # necessidades automaticas supridas
    pool: PoolChampion | None = None

    @property
    def champion(self) -> Champion:
        return self.entry.champion

    @property
    def score(self) -> float:
        score = self.entry.win_rate - 0.5 + sum(self.synergy.values())
        if self.versus is not None:
            score += self.versus - 0.5
        return score + config.COMPOSITION_BONUS * len(self.fills)


@dataclass
class PickResult:
    position: str
    allies: list[Ally]
    required: list[str]  # necessidades ditas pelo jogador (filtro)
    gaps: list[str]  # necessidades deduzidas da composicao (bonus)
    enemy: Champion | None
    options: list[PickOption]


class DraftAdvisor:
    def __init__(self, counters: CounterAdvisor, meta: MetaAdvisor, profiles: ProfileStore):
        self.counters = counters
        self.meta = meta
        self.profiles = profiles
        self.mcp = counters.mcp
        self._executor = ThreadPoolExecutor(max_workers=4)

    def main_position(self, champion: Champion) -> str | None:
        return self.meta.main_position(champion)

    def warm_up(self) -> None:
        self.profiles.ensure_all(self.main_position)

    # --- Ban ---------------------------------------------------------------

    def bans_against(self, mine: Champion, position: str) -> list[BanTarget]:
        """Quem mais ameaca `mine` na rota, da maior ameaca pra menor."""
        lane = self.meta.lane(position)
        targets = []
        for pick in self.counters.counters(mine, position):
            entry = lane.get(pick.champion.id)
            if entry and pick.win_rate > 0.5:
                targets.append(BanTarget(pick.champion, pick.win_rate, entry.pick_rate, counter=pick))
        return sorted(targets, key=lambda t: t.threat, reverse=True)

    def bans_for_lane(self, position: str) -> list[BanTarget]:
        """Os mais perigosos da rota em geral."""
        targets = [BanTarget(e.champion, e.win_rate, e.pick_rate)
                   for e in self.meta.ranking(position, config.META_MIN_PICK_RATE)
                   if e.win_rate > 0.5]
        return sorted(targets, key=lambda t: t.threat, reverse=True)

    # --- Pick --------------------------------------------------------------

    def pick(self, position: str, allies: list[tuple[Champion, str | None]],
             required: list[str], enemy: Champion | None = None) -> PickResult:
        team = self._place_allies(position, allies)
        profiles = self.profiles.ensure([a.champion for a in team], self.main_position)
        for ally in team:
            ally.profile = profiles.get(ally.champion.id)
        gaps = [g for g in composition_gaps(team) if g not in required]

        # Tudo que depende da rede sai em paralelo.
        synergy_futures = {a.champion.name: self._executor.submit(self._synergy_with, a, position)
                           for a in team}
        versus_future = (self._executor.submit(self.counters.counters, enemy, position)
                         if enemy else None)

        pool = {p.champion.id: p for p in self.counters.player_pool()}
        ally_ids = {a.champion.id for a in team} | ({enemy.id} if enemy else set())
        lane = self.meta.lane(position)
        candidates = [e for e in lane.values()
                      if e.champion.id not in ally_ids
                      and (e.pick_rate >= config.PICK_MIN_PICK_RATE
                           or (e.champion.id in pool and e.pick_rate > 0))]
        candidate_profiles = self.profiles.ensure([e.champion for e in candidates], self.main_position)

        versus = {}
        if versus_future:
            versus = {p.champion.id: p.win_rate for p in versus_future.result()}
        synergies = {name: future.result() for name, future in synergy_futures.items()}

        options = []
        for entry in candidates:
            profile = candidate_profiles.get(entry.champion.id)
            if required and not (profile and all(profile.fills(n) for n in required)):
                continue
            option = PickOption(
                entry, profile,
                synergy={name: table[entry.champion.id]
                         for name, table in synergies.items() if entry.champion.id in table},
                versus=versus.get(entry.champion.id),
                fills=[g for g in gaps if profile and profile.fills(g)],
                pool=pool.get(entry.champion.id),
            )
            options.append(option)
        options.sort(key=lambda o: o.score, reverse=True)
        return PickResult(position, team, required, gaps, enemy, options)

    def enemy_position(self, enemy: Champion) -> str:
        """Rota do confronto quando o jogador nao diz: a dele (config) se o
        adversario joga la' com alguma frequencia, senao a principal do
        adversario ("to contra a Leona" = suporte, nao top)."""
        rates = self.meta.role_rates(enemy)
        if rates.get(config.MAIN_POSITION, 0) >= MAIN_LANE_MIN_ROLE_RATE:
            return config.MAIN_POSITION
        return self.main_position(enemy) or config.MAIN_POSITION

    def my_position(self, allies: list[tuple[Champion, str | None]]) -> str:
        """Rota do jogador quando ele nao diz. Com 3+ aliados (ou a rota dele
        ja' ocupada por um aliado que disse a rota), e' a que sobra na
        combinacao mais provavel do time: Darius, Lee Sin, Ahri e Jinx = suporte."""
        stated = {p for _, p in allies if p}
        if len(allies) < 3 and config.MAIN_POSITION not in stated:
            return config.MAIN_POSITION
        options = [p for p in POSITIONS if p not in stated] or POSITIONS
        return max(options, key=lambda p: (self._assignment(p, allies)[1], p == config.MAIN_POSITION))

    def _place_allies(self, position: str, allies: list[tuple[Champion, str | None]]) -> list[Ally]:
        return self._assignment(position, allies)[0]

    def _assignment(self, position: str, allies: list[tuple[Champion, str | None]]) -> tuple[list[Ally], float]:
        """Da' uma rota a cada aliado: a dita, ou a combinacao mais provavel
        entre as que sobram (o time tem uma pessoa por rota). Devolve tambem
        a log-probabilidade da combinacao, pra comparar rotas do jogador."""
        allies = [(c, p if p != position else None) for c, p in allies][:len(POSITIONS) - 1]
        taken = {position} | {p for _, p in allies if p}
        fixed = [Ally(c, p, guessed=False) for c, p in allies if p]
        free = [c for c, p in allies if not p]
        open_lanes = [p for p in POSITIONS if p not in taken]

        best, best_score = (), -math.inf
        for lanes in itertools.permutations(open_lanes, len(free)):
            score = sum(math.log(max(self.meta.role_rates(c).get(lane, 0), ROLE_RATE_FLOOR))
                        for c, lane in zip(free, lanes))
            if score > best_score:
                best, best_score = lanes, score
        return fixed + [Ally(c, lane, guessed=True) for c, lane in zip(free, best)], best_score

    def _synergy_with(self, ally: Ally, position: str) -> dict[int, float]:
        """{id do candidato: delta de winrate por jogar com `ally`} (media das fontes)."""
        deltas: dict[int, list[float]] = {}

        try:
            table = lolalytics.synergies(ally.champion, ally.position).get(position, {})
        except lolalytics.LolalyticsError as exc:
            print(f"[Enzo] Sinergia do Lolalytics indisponivel: {exc}")
            table = {}
        for champion_id, synergy in table.items():
            if synergy.games >= MIN_SYNERGY_GAMES:
                deltas.setdefault(champion_id, []).append(shrink(synergy.delta, synergy.games))

        for champion_id, delta in self._opgg_synergy(ally, position).items():
            deltas.setdefault(champion_id, []).append(delta)

        return {k: sum(v) / len(v) for k, v in deltas.items()}

    def _opgg_synergy(self, ally: Ally, position: str) -> dict[int, float]:
        """Winrate da dupla menos o esperado (winrates individuais somados), pro
        delta ficar na mesma escala do Lolalytics."""
        try:
            result = self.mcp.call_tool("lol_get_champion_synergies", {
                "champion": ally.champion.mcp_name,
                "my_position": ally.position,
                "synergy_position": position,
                "desired_output_fields": ["data.synergies[].{synergy_champion_id,play,win}"],
            })
        except McpError as exc:
            print(f"[Enzo] Sinergia do OP.GG indisponivel: {exc}")
            return {}
        ally_entry = self.meta.lane(ally.position).get(ally.champion.id)
        lane = self.meta.lane(position)
        deltas = {}
        for row in (result.get("data") or {}).get("synergies") or []:
            entry = lane.get(row["synergy_champion_id"])
            if not (entry and entry.opgg and ally_entry and ally_entry.opgg):
                continue
            if row["play"] >= MIN_SYNERGY_GAMES:
                expected = ally_entry.opgg.win_rate + entry.opgg.win_rate - 0.5
                deltas[entry.champion.id] = shrink(row["win"] / row["play"] - expected, row["play"])
        return deltas


def shrink(delta: float, games: int) -> float:
    return delta * games / (games + SYNERGY_PRIOR_GAMES)


def composition_gaps(team: list[Ally]) -> list[str]:
    """O que falta no time, pelos perfis conhecidos. So' conclui algo com
    aliados suficientes (com 1 ou 2 ainda e' cedo pra dizer que falta tanque)."""
    profiles = [a.profile for a in team if a.profile]
    gaps = []
    if len(profiles) >= 2 and not any(p.is_carry for p in profiles):
        gaps.append(NEED_CARRY)
    if len(profiles) >= 3 and not any(p.is_tank for p in profiles):
        gaps.append(NEED_TANK)
    typed = [p for p in profiles if p.damage_type]
    if len(typed) >= 2 and not any(p.deals_ap for p in typed):
        gaps.append(NEED_AP)
    if len(typed) >= 2 and not any(p.deals_ad for p in typed):
        gaps.append(NEED_AD)
    return gaps


# --- Relatorios pro console --------------------------------------------------

def _pct(rate: float) -> str:
    return f"{rate:5.1%}"


def _delta(rate: float) -> str:
    return f"{rate * 100:+.1f}"


def format_meta(position: str, entries: list[LaneEntry], pool_ids: set[int]) -> str:
    lines = [f"Meta no {position} [tiers | winrate medio | pick rate medio] "
             f"(Lolalytics {config.LOLALYTICS_TIER}):"]
    width = max((len(e.champion.name) for e in entries[:config.META_CONSOLE]), default=0)
    for i, entry in enumerate(entries, 1):
        mine = entry.champion.id in pool_ids
        if i > config.META_CONSOLE and not mine:
            continue
        lines.append(f"  {i:>2}. {entry.champion.name:<{width}}  {tier_label(entry)} | "
                     f"WR {_pct(entry.win_rate)} | PR {_pct(entry.pick_rate)}"
                     + ("  <- voce joga" if mine else ""))
    return "\n".join(lines)


def format_bans(title: str, targets: list[BanTarget]) -> str:
    lines = [f"{title} [ameaca = pick rate x (winrate - 50%)]:"]
    width = max((len(t.champion.name) for t in targets[:config.BANS_CONSOLE]), default=0)
    for i, t in enumerate(targets[:config.BANS_CONSOLE], 1):
        sources = ""
        if t.counter:
            opgg = _pct(t.counter.opgg.win_rate) if t.counter.opgg else "  -  "
            lol = _pct(t.counter.lolalytics.win_rate) if t.counter.lolalytics else "  -  "
            sources = f" (OP.GG {opgg} | Lolalytics {lol})"
        lines.append(f"  {i:>2}. {t.champion.name:<{width}}  ameaca {t.threat * 1000:4.1f} | "
                     f"WR {_pct(t.win_rate)}{sources} | PR {_pct(t.pick_rate)}")
    if not targets:
        lines.append("  (nenhum campeao com vantagem e amostra suficiente)")
    return "\n".join(lines)


def format_pick(result: PickResult) -> str:
    allies = ", ".join(f"{a.champion.name} ({a.position}{'?' if a.guessed else ''})"
                       for a in result.allies) or "nenhum aliado citado"
    lines = [f"Pick pro {result.position} | time: {allies}"]
    if result.required:
        lines.append("  Filtro: " + ", ".join(NEED_LABELS[n] for n in result.required))
    if result.gaps:
        lines.append(f"  Falta no time (+{config.COMPOSITION_BONUS:.0%} cada): "
                     + ", ".join(NEED_LABELS[n] for n in result.gaps))
    lines.append("  [nota = (WR na rota - 50%) + sinergias + confronto + composicao]")
    width = max((len(o.champion.name) for o in result.options[:config.PICK_CONSOLE]), default=0)
    for i, option in enumerate(result.options, 1):
        if i > config.PICK_CONSOLE and not option.pool:
            continue
        parts = [f"rota {_delta(option.entry.win_rate - 0.5)}"]
        parts += [f"{name} {_delta(d)}" for name, d in option.synergy.items()]
        if option.versus is not None:
            parts.append(f"vs {result.enemy.name} {_delta(option.versus - 0.5)}")
        if option.fills:
            parts.append("supre " + "/".join(NEED_LABELS[n] for n in option.fills))
        mark = f"  <- voce joga: {personal_summary(option.pool)}" if option.pool else ""
        lines.append(f"  {i:>2}. {option.champion.name:<{width}}  {_delta(option.score):>5} "
                     f"= {', '.join(parts)}{mark}")
    if not result.options:
        lines.append("  (nenhum candidato com dados que atenda o pedido)")
    return "\n".join(lines)
