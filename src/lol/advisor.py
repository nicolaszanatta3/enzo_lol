"""Counters de um campeao inimigo, com as metricas de cada fonte e o pool do jogador.

Na hora da pergunta, busca em paralelo a tabela de confrontos DO INIMIGO na rota:
  - OP.GG (lol_get_lane_matchup_guide): `counters` traz o desempenho do
    campeao contra TODOS os adversarios da rota, com partidas e vitorias;
  - Lolalytics (endpoint "counter" da API, filtrado por rota e elo).
Quem mais ganha do inimigo e' o melhor counter. Cada counter leva os numeros
das duas fontes e, se estiver no pool do jogador, o historico dele.

O pool (mais jogados na season pelo OP.GG + maiores maestrias pela API da
Riot) e a lista de campeoes sao carregados antes da pergunta (`warm_up`).
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

from src.core import config
from src.lol import champions, lolalytics, riot_api
from src.lol.champions import Champion
from src.lol.opgg_mcp import McpError, OpggMcpClient

MIN_MATCHUP_GAMES = 100  # por fonte; abaixo disso a amostra e' pequena demais (e' o corte do Lolalytics)
POOL_CACHE_SECONDS = 30 * 60
COUNTERS_CACHE_SECONDS = 30 * 60


@dataclass
class PoolChampion:
    champion: Champion
    games: int = 0  # partidas ranqueadas na season (OP.GG)
    wins: int = 0
    mastery_points: int = 0


@dataclass
class Source:
    games: int
    win_rate: float  # do counter contra o inimigo, de 0 a 1


@dataclass
class CounterPick:
    champion: Champion
    opgg: Source | None = None
    lolalytics: Source | None = None
    pool: PoolChampion | None = None  # preenchido se o jogador joga esse campeao

    @property
    def sources(self) -> list[Source]:
        return [s for s in (self.opgg, self.lolalytics) if s is not None]

    @property
    def win_rate(self) -> float:
        """Media simples das fontes (amostras e elos diferentes, entao nenhuma
        pesa mais so' por ter mais partidas)."""
        return sum(s.win_rate for s in self.sources) / len(self.sources)


class CounterAdvisor:
    def __init__(self):
        self.mcp = OpggMcpClient()
        self._pool: list[PoolChampion] | None = None
        self._pool_loaded_at = 0.0
        # (id do inimigo, rota) -> (quando buscou, counters sem o pool)
        self._counters: dict[tuple[int, str], tuple[float, list[CounterPick]]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)

    def warm_up(self) -> None:
        """Carrega lista de campeoes e pool. Chame no inicio, em background."""
        champions.list_champions(self.mcp)
        self.player_pool()

    # --- Pool do jogador ---------------------------------------------------

    def player_pool(self) -> list[PoolChampion]:
        with self._lock:
            if self._pool is None or time.time() - self._pool_loaded_at > POOL_CACHE_SECONDS:
                self._pool = self._load_pool()
                self._pool_loaded_at = time.time()
            return self._pool

    def _load_pool(self) -> list[PoolChampion]:
        pool: dict[int, PoolChampion] = {}

        try:
            profile = self.mcp.call_tool("lol_get_summoner_profile", {
                "game_name": config.RIOT_GAME_NAME,
                "tag_line": config.RIOT_TAG_LINE,
                "region": config.OPGG_REGION,
                "desired_output_fields": [
                    "data.summoner.most_champions.champion_stats[].{champion_name,play,win}",
                ],
            })
            stats = profile["data"]["summoner"]["most_champions"]["champion_stats"]
        except (McpError, httpx.HTTPError, KeyError, TypeError) as exc:
            print(f"[Enzo] Perfil do OP.GG indisponivel, usando so as maestrias: {exc}")
            stats = []
        for stat in stats[:config.POOL_SIZE]:
            champion = champions.by_name(self.mcp, stat["champion_name"])
            if champion:
                pool[champion.id] = PoolChampion(champion, games=stat["play"], wins=stat["win"])

        try:
            puuid = riot_api.get_puuid(config.RIOT_GAME_NAME, config.RIOT_TAG_LINE)
            masteries = riot_api.get_top_masteries(puuid, count=config.POOL_SIZE)
        except riot_api.RiotApiError as exc:
            print(f"[Enzo] Maestrias indisponiveis, usando so o OP.GG: {exc}")
            masteries = []
        champion_by_id = champions.by_id(self.mcp)
        for mastery in masteries:
            champion = champion_by_id.get(mastery["championId"])
            if champion is None:
                continue
            entry = pool.setdefault(champion.id, PoolChampion(champion))
            entry.mastery_points = mastery["championPoints"]

        return list(pool.values())

    # --- Counters ----------------------------------------------------------

    def counters(self, enemy: Champion, position: str) -> list[CounterPick]:
        """Todos os counters do inimigo na rota, do melhor pro pior, com o
        pool do jogador marcado."""
        key = (enemy.id, position)
        cached = self._counters.get(key)
        if cached is None or time.time() - cached[0] > COUNTERS_CACHE_SECONDS:
            cached = (time.time(), self._fetch_counters(enemy, position))
            self._counters[key] = cached

        pool = {p.champion.id: p for p in self.player_pool()}
        picks = [CounterPick(c.champion, c.opgg, c.lolalytics, pool.get(c.champion.id))
                 for c in cached[1]]
        return sorted(picks, key=lambda p: p.win_rate, reverse=True)

    def _fetch_counters(self, enemy: Champion, position: str) -> list[CounterPick]:
        opgg_future = self._executor.submit(self._fetch_opgg_table, enemy, position)
        lolalytics_future = self._executor.submit(lolalytics.counters, enemy, position)

        picks: dict[int, CounterPick] = {}
        champion_by_id = champions.by_id(self.mcp)
        for opponent_id, (games, enemy_wins) in opgg_future.result().items():
            opponent = champion_by_id.get(opponent_id)
            if opponent and games >= MIN_MATCHUP_GAMES:
                picks[opponent.id] = CounterPick(opponent, opgg=Source(games, 1 - enemy_wins / games))

        try:
            table = lolalytics_future.result()
        except lolalytics.LolalyticsError as exc:
            print(f"[Enzo] Lolalytics indisponivel, usando so o OP.GG: {exc}")
            table = {}
        for opponent_id, (games, enemy_rate) in table.items():
            opponent = champion_by_id.get(opponent_id)
            if opponent and opponent.id != enemy.id and games >= MIN_MATCHUP_GAMES:
                pick = picks.setdefault(opponent.id, CounterPick(opponent))
                pick.lolalytics = Source(games, 1 - enemy_rate)

        return list(picks.values())

    def _fetch_opgg_table(self, champion: Champion, position: str) -> dict[int, tuple[int, int]]:
        """{id do adversario: (partidas, vitorias de `champion`)}. O oponente e'
        obrigatorio na ferramenta mas nao muda a lista `counters`; usa qualquer
        campeao diferente."""
        any_opponent = next(c for c in champions.list_champions(self.mcp) if c.id != champion.id)
        try:
            guide = self.mcp.call_tool("lol_get_lane_matchup_guide", {
                "my_champion": champion.mcp_name,
                "opponent_champion": any_opponent.mcp_name,
                "position": position,
            })
        except McpError as exc:
            print(f"[Enzo] OP.GG sem dados de {champion.name} no {position}: {exc}")
            return {}
        rows = (guide.get("data") or {}).get("counters") or []
        return {r["champion_id"]: (r["play"], r["win"]) for r in rows}

    def matchup_tip(self, mine: Champion, enemy: Champion, position: str) -> str | None:
        """Dica do OP.GG (em ingles) pra esse confronto especifico."""
        try:
            guide = self.mcp.call_tool("lol_get_lane_matchup_guide", {
                "my_champion": mine.mcp_name,
                "opponent_champion": enemy.mcp_name,
                "position": position,
            })
        except McpError:
            return None
        return (guide.get("data") or {}).get("opponent_champion_tip")


def best_from_pool(picks: list[CounterPick]) -> CounterPick | None:
    return next((p for p in picks if p.pool), None)


def personal_summary(pool: PoolChampion) -> str:
    if pool.games:
        return f"{pool.wins}V {pool.games - pool.wins}D na season"
    return f"{pool.mastery_points:,} pts de maestria".replace(",", ".")


def _format_source(label: str, source: Source | None) -> str:
    if source is None:
        return f"{label}    -    "
    games = f"{source.games:,}".replace(",", ".")
    return f"{label} {source.win_rate:5.1%} ({games})"


def format_report(enemy: Champion, position: str, picks: list[CounterPick]) -> str:
    """Texto detalhado pro console: todas as metricas + o pool do jogador."""
    lines = [
        f"Contra {enemy.name} ({position}) - winrate do counter contra ele "
        f"[media | OP.GG | Lolalytics {config.LOLALYTICS_TIER}], (partidas):"
    ]
    width = max((len(p.champion.name) for p in picks), default=0)
    for i, pick in enumerate(picks, 1):
        if i > config.COUNTERS_CONSOLE and not pick.pool:
            continue  # alem do top, so' mostra quem o jogador joga
        mark = f"  <- voce joga: {personal_summary(pick.pool)}" if pick.pool else ""
        lines.append(
            f"  {i:>2}. {pick.champion.name:<{width}}  {pick.win_rate:5.1%} | "
            f"{_format_source('OP.GG', pick.opgg)} | "
            f"{_format_source('Lolalytics', pick.lolalytics)}{mark}"
        )
    if not best_from_pool(picks):
        lines.append("  (nenhum campeao do seu pool tem dados contra ele nessa rota)")
    return "\n".join(lines)
