"""Tier list por rota, cruzando OP.GG e Lolalytics.

  - OP.GG (lol_list_lane_meta_champions): UMA chamada traz todas as rotas,
    com tier (1=OP ... 5=fraco), partidas, vitorias, pick/ban rate e
    `role_rate` (quanto das partidas do campeao sao naquela rota). O
    role_rate tambem serve pra deduzir a rota dos aliados.
  - Lolalytics (endpoint "list"): tier de 1 (S+) a 15 (D-), no elo configurado.

Cada fonte tem sua escala; pra ordenar, o tier vira uma posicao de 0 (melhor)
a 1 (pior) e tira-se a media das fontes que tem o campeao.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from src.lol import champions, lolalytics
from src.lol.champions import Champion
from src.lol.opgg_mcp import OpggMcpClient

POSITIONS = ["top", "jungle", "mid", "adc", "support"]
META_CACHE_SECONDS = 30 * 60
OPGG_WORST_TIER = 5
LOLALYTICS_WORST_TIER = 15


@dataclass
class MetaSource:
    tier: int  # na escala da fonte; 0 = sem tier
    win_rate: float
    pick_rate: float
    ban_rate: float
    games: int
    worst_tier: int

    @property
    def tier_position(self) -> float | None:
        """0 = melhor tier da fonte, 1 = pior; None se a fonte nao da tier."""
        return (self.tier - 1) / (self.worst_tier - 1) if self.tier else None


@dataclass
class LaneEntry:
    champion: Champion
    opgg: MetaSource | None = None
    lolalytics: MetaSource | None = None

    @property
    def sources(self) -> list[MetaSource]:
        return [s for s in (self.opgg, self.lolalytics) if s is not None]

    @property
    def win_rate(self) -> float:
        return sum(s.win_rate for s in self.sources) / len(self.sources)

    @property
    def pick_rate(self) -> float:
        return sum(s.pick_rate for s in self.sources) / len(self.sources)

    @property
    def tier_position(self) -> float | None:
        positions = [s.tier_position for s in self.sources if s.tier_position is not None]
        return sum(positions) / len(positions) if positions else None


class MetaAdvisor:
    def __init__(self, mcp: OpggMcpClient):
        self.mcp = mcp
        # rota -> (quando buscou, {id: LaneEntry})
        self._lanes: dict[str, tuple[float, dict[int, LaneEntry]]] = {}
        self._lane_locks: dict[str, threading.Lock] = {}
        self._opgg: tuple[float, dict[str, dict[int, tuple[MetaSource, float]]]] | None = None
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)

    # --- OP.GG: todas as rotas numa chamada ---------------------------------

    def _opgg_all(self) -> dict[str, dict[int, tuple[MetaSource, float]]]:
        """{rota: {id: (MetaSource, role_rate)}}."""
        with self._lock:
            if self._opgg is None or time.time() - self._opgg[0] > META_CACHE_SECONDS:
                self._opgg = (time.time(), self._fetch_opgg())
            return self._opgg[1]

    def _fetch_opgg(self) -> dict[str, dict[int, tuple[MetaSource, float]]]:
        fields = "{champion,tier,play,win,pick_rate,ban_rate,role_rate,is_rip}"
        result = self.mcp.call_tool("lol_list_lane_meta_champions", {
            "position": "all",
            "desired_output_fields": [f"data.positions.{p}[].{fields}" for p in POSITIONS],
        })
        positions = (result.get("data") or {}).get("positions") or {}
        table = {}
        for position in POSITIONS:
            by_id = {}
            for row in positions.get(position) or []:
                champion = champions.by_name(self.mcp, row["champion"])
                if champion is None or not row["play"]:
                    continue
                source = MetaSource(
                    tier=0 if row.get("is_rip") else row["tier"],
                    win_rate=row["win"] / row["play"],
                    pick_rate=row["pick_rate"],
                    ban_rate=row["ban_rate"],
                    games=row["play"],
                    worst_tier=OPGG_WORST_TIER,
                )
                by_id[champion.id] = (source, row["role_rate"])
            table[position] = by_id
        return table

    def role_rates(self, champion: Champion) -> dict[str, float]:
        """Fracao das partidas do campeao em cada rota (OP.GG)."""
        return {position: rows[champion.id][1]
                for position, rows in self._opgg_all().items() if champion.id in rows}

    def main_position(self, champion: Champion) -> str | None:
        rates = self.role_rates(champion)
        return max(rates, key=rates.get) if rates else None

    # --- Rota: as duas fontes juntas ---------------------------------------

    def lane(self, position: str) -> dict[int, LaneEntry]:
        """Todos os campeoes com dados na rota, por id."""
        # Um lock por rota: varios aliados pedem a mesma rota ao mesmo tempo.
        with self._lock:
            lane_lock = self._lane_locks.setdefault(position, threading.Lock())
        with lane_lock:
            cached = self._lanes.get(position)
            if cached is None or time.time() - cached[0] > META_CACHE_SECONDS:
                cached = (time.time(), self._fetch_lane(position))
                self._lanes[position] = cached
            return cached[1]

    def _fetch_lane(self, position: str) -> dict[int, LaneEntry]:
        lolalytics_future = self._executor.submit(lolalytics.lane_stats, position)
        entries: dict[int, LaneEntry] = {}
        for champion_id, (source, _) in self._opgg_all().get(position, {}).items():
            entries[champion_id] = LaneEntry(champions.by_id(self.mcp)[champion_id], opgg=source)

        try:
            table = lolalytics_future.result()
        except lolalytics.LolalyticsError as exc:
            print(f"[Enzo] Lolalytics indisponivel, usando so o OP.GG: {exc}")
            table = {}
        champion_by_id = champions.by_id(self.mcp)
        for champion_id, stats in table.items():
            champion = champion_by_id.get(champion_id)
            if champion is None or not stats.games:
                continue
            entry = entries.setdefault(champion_id, LaneEntry(champion))
            entry.lolalytics = MetaSource(stats.tier, stats.win_rate, stats.pick_rate,
                                          stats.ban_rate, stats.games, LOLALYTICS_WORST_TIER)
        return entries

    def ranking(self, position: str, min_pick_rate: float) -> list[LaneEntry]:
        """Campeoes com tier em alguma fonte e jogados o bastante na rota, do
        mais forte pro mais fraco (tier medio; empate pelo winrate)."""
        entries = [e for e in self.lane(position).values()
                   if e.tier_position is not None and e.pick_rate >= min_pick_rate]
        return sorted(entries, key=lambda e: (e.tier_position, -e.win_rate))


def tier_label(entry: LaneEntry) -> str:
    """Ex: "OP.GG T1 | Lolalytics S+"."""
    opgg = f"T{entry.opgg.tier}" if entry.opgg and entry.opgg.tier else "-"
    lol = lolalytics.TIER_LABELS[entry.lolalytics.tier] if entry.lolalytics else "-"
    return f"OP.GG {opgg:<2} | Lolalytics {lol:<2}"
