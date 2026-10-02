"""Build e runas de um campeao numa rota (OP.GG, lol_get_champion_analysis).

Uma chamada (~5-10s) traz itens iniciais, botas, itens core, opcoes de 4o a
6o item, feiticos, ordem de habilidades e a pagina de runas mais jogada.
Aqui so' ficam ids e numeros; nomes e imagens vem do Data Dragon
(src/web/ddragon.py), que ja' tem tudo em portugues.
"""

import threading
import time
from dataclasses import dataclass, field

from src.lol.champions import Champion
from src.lol.opgg_mcp import OpggMcpClient

BUILD_CACHE_SECONDS = 30 * 60
ITEM_FIELDS = "{ids[],pick_rate,play,win}"
FIELDS = [
    f"data.starter_items.{ITEM_FIELDS}",
    f"data.boots.{ITEM_FIELDS}",
    f"data.core_items.{ITEM_FIELDS}",
    f"data.fourth_items[].{ITEM_FIELDS}",
    f"data.fifth_items[].{ITEM_FIELDS}",
    f"data.sixth_items[].{ITEM_FIELDS}",
    f"data.summoner_spells.{ITEM_FIELDS}",
    "data.skills.{order[],pick_rate,play,win}",
    "data.skill_masteries.{ids[],pick_rate,play,win}",
    "data.runes.{primary_page_id,primary_rune_ids[],secondary_page_id,secondary_rune_ids[],"
    "stat_mod_ids[],pick_rate,play,win}",
    "data.summary.average_stats.{ban_rate,kda,pick_rate,play,rank,tier,win_rate}",
]


@dataclass
class Option:
    """Um conjunto de itens/feiticos/habilidades e o quanto e' jogado."""
    ids: list
    games: int
    win_rate: float
    pick_rate: float


@dataclass
class Runes:
    primary_tree: int
    primary: list[int]  # keystone + 3
    secondary_tree: int
    secondary: list[int]  # 2
    shards: list[int]  # ataque, flex, defesa
    games: int
    win_rate: float
    pick_rate: float


@dataclass
class Build:
    tier: int  # OP.GG: 1 (OP) a 5
    rank: int
    win_rate: float
    pick_rate: float
    ban_rate: float
    kda: float
    games: int
    starter: Option | None = None
    boots: Option | None = None
    core: Option | None = None
    fourth: list[Option] = field(default_factory=list)
    fifth: list[Option] = field(default_factory=list)
    sixth: list[Option] = field(default_factory=list)
    spells: Option | None = None
    skill_order: Option | None = None  # ids = ["Q", "W", ...] nivel a nivel
    skill_priority: Option | None = None  # ids = ["Q", "E", "W"]
    runes: Runes | None = None


def _option(row: dict | None, key: str = "ids") -> Option | None:
    if not row or not row.get("play"):
        return None
    return Option(row.get(key) or [], row["play"], row["win"] / row["play"], row.get("pick_rate") or 0)


class BuildAdvisor:
    def __init__(self, mcp: OpggMcpClient):
        self.mcp = mcp
        self._cache: dict[tuple[int, str], tuple[float, Build]] = {}
        self._locks: dict[tuple[int, str], threading.Lock] = {}
        self._lock = threading.Lock()

    def build(self, champion: Champion, position: str) -> Build:
        key = (champion.id, position)
        with self._lock:
            key_lock = self._locks.setdefault(key, threading.Lock())
        with key_lock:  # duas abas pedindo o mesmo campeao: uma chamada so'
            cached = self._cache.get(key)
            if cached is None or time.time() - cached[0] > BUILD_CACHE_SECONDS:
                cached = (time.time(), self._fetch(champion, position))
                self._cache[key] = cached
            return cached[1]

    def _fetch(self, champion: Champion, position: str) -> Build:
        result = self.mcp.call_tool("lol_get_champion_analysis", {
            "champion": champion.mcp_name,
            "position": position,
            "game_mode": "ranked",
            "desired_output_fields": FIELDS,
        })
        data = result.get("data") or {}
        stats = ((data.get("summary") or {}).get("average_stats")) or {}
        build = Build(
            tier=stats.get("tier") or 0,
            rank=stats.get("rank") or 0,
            win_rate=stats.get("win_rate") or 0,
            pick_rate=stats.get("pick_rate") or 0,
            ban_rate=stats.get("ban_rate") or 0,
            kda=stats.get("kda") or 0,
            games=stats.get("play") or 0,
            starter=_option(data.get("starter_items")),
            boots=_option(data.get("boots")),
            core=_option(data.get("core_items")),
            fourth=[o for o in map(_option, data.get("fourth_items") or []) if o],
            fifth=[o for o in map(_option, data.get("fifth_items") or []) if o],
            sixth=[o for o in map(_option, data.get("sixth_items") or []) if o],
            spells=_option(data.get("summoner_spells")),
            skill_order=_option(data.get("skills"), "order"),
            skill_priority=_option(data.get("skill_masteries")),
        )
        runes = data.get("runes")
        if runes and runes.get("play"):
            build.runes = Runes(
                runes["primary_page_id"], runes.get("primary_rune_ids") or [],
                runes["secondary_page_id"], runes.get("secondary_rune_ids") or [],
                runes.get("stat_mod_ids") or [],
                runes["play"], runes["win"] / runes["play"], runes.get("pick_rate") or 0,
            )
        return build
