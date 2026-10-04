"""Build e runas de um campeao numa rota: no geral ou contra um adversario.

Geral: o OP.GG (lol_get_champion_analysis, ~3s) da' a opcao mais jogada de
cada parte e as opcoes de 4o a 6o item; o Lolalytics ("build-full", ~1s, em
paralelo) completa com alternativas: outros itens iniciais, botas e feiticos,
opcoes de 1o a 3o item e as paginas de runa mais jogada e que mais vence.

Contra um adversario: lol_get_lane_matchup_guide do OP.GG (~3s) ja' traz
varias opcoes de tudo, contando so' as partidas daquele confronto, mais uma
dica, o estilo de jogo recomendado e quem leva vantagem na rota.

Aqui so' ficam ids e numeros; nomes e imagens vem do Data Dragon
(src/web/ddragon.py), que ja' tem tudo em portugues.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from src.lol import lolalytics
from src.lol.champions import Champion
from src.lol.opgg_mcp import OpggMcpClient

BUILD_CACHE_SECONDS = 30 * 60
MAX_OPTIONS = 3  # por parte da build: a principal + alternativas
MIN_PICK_RATE = 0.02  # alternativa mais rara que isso e' ruido
MIN_GAMES = 30  # idem, nas amostras pequenas de um confronto
IGNORED_BOOTS = {1001, 9999}  # Lolalytics: botas basicas e "sem bota"

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
class RunePage:
    primary_tree: int
    primary: list[int]  # keystone + 3
    secondary_tree: int
    secondary: list[int]  # 2
    shards: list[int]  # ataque, flex, defesa
    games: int
    win_rate: float
    pick_rate: float
    label: str = ""  # de onde veio, ex: "Maior vitória · Lolalytics"


@dataclass
class Build:
    tier: int = 0  # OP.GG: 1 (OP) a 5
    rank: int = 0
    win_rate: float = 0
    pick_rate: float = 0
    ban_rate: float = 0
    kda: float = 0
    games: int = 0
    # Cada parte: a opcao principal primeiro, depois as alternativas.
    starters: list[Option] = field(default_factory=list)
    boots: list[Option] = field(default_factory=list)
    core: list[Option] = field(default_factory=list)
    item_slots: list[list[Option]] = field(default_factory=list)  # opcoes do 1o, 2o... item
    spells: list[Option] = field(default_factory=list)
    skill_order: Option | None = None  # ids = ["Q", "W", ...] nivel a nivel
    skill_priority: Option | None = None  # ids = ["Q", "E", "W"]
    runes: list[RunePage] = field(default_factory=list)


@dataclass
class Matchup:
    build: Build  # so' com as partidas desse confronto
    games: int
    win_rate: float | None  # do campeao do jogador contra o adversario (OP.GG)
    tip: str | None  # em ingles
    play_style: str | None  # "aggressive", "defensive" ou "even"
    lane_advantage: str | None  # nome (OP.GG) de quem ganha a rota
    solo_kill_advantage: str | None  # de quem consegue mais abates solo


# --- Interpretacao -----------------------------------------------------------

def _option(row: dict | None, key: str = "ids") -> Option | None:
    if not row or not row.get("play"):
        return None
    return Option(row.get(key) or [], row["play"], row["win"] / row["play"], row.get("pick_rate") or 0)


def _top(options: list) -> list:
    """As mais jogadas sem as raras; se todas forem raras, ao menos a mais jogada."""
    options = sorted(options, key=lambda o: o.games, reverse=True)
    common = [o for o in options if o.pick_rate >= MIN_PICK_RATE and o.games >= MIN_GAMES]
    return common[:MAX_OPTIONS] or options[:1]


def _options(rows: list | None, key: str = "ids") -> list[Option]:
    return _top([o for o in (_option(r, key) for r in rows or []) if o])


def _opgg_page(row: dict | None, label: str = "") -> RunePage | None:
    if not row or not row.get("play"):
        return None
    return RunePage(
        row["primary_page_id"], row.get("primary_rune_ids") or [],
        row["secondary_page_id"], row.get("secondary_rune_ids") or [],
        row.get("stat_mod_ids") or [],
        row["play"], row["win"] / row["play"], row.get("pick_rate") or 0, label,
    )


def _stats(build: Build, summary: dict | None) -> Build:
    stats = ((summary or {}).get("average_stats")) or {}
    build.tier = stats.get("tier") or 0
    build.rank = stats.get("rank") or 0
    build.win_rate = stats.get("win_rate") or 0
    build.pick_rate = stats.get("pick_rate") or 0
    build.ban_rate = stats.get("ban_rate") or 0
    build.kda = stats.get("kda") or 0
    build.games = stats.get("play") or 0
    return build


def _lolalytics_options(rows: list | None, ignored: set[int] = frozenset()) -> list[Option]:
    """Linhas [ids, wr, pr, n, ...] do Lolalytics; ids juntos por "_"."""
    options = []
    for row in rows or []:
        try:
            ids = [int(i) for i in str(row[0]).split("_") if i]  # "" = comecou sem item
            option = Option(ids, int(row[3]), row[1] / 100, row[2] / 100)
        except (IndexError, TypeError, ValueError):
            continue
        if ids and not ignored.intersection(ids):
            options.append(option)
    return _top(options)


def _lolalytics_page(summary: dict | None, total: int, label: str) -> RunePage | None:
    runes = (summary or {}).get("runes") or {}
    page, chosen = runes.get("page") or {}, runes.get("set") or {}
    try:
        primary_tree = lolalytics.RUNE_TREES[page["pri"]]
        secondary_tree = lolalytics.RUNE_TREES[page["sec"]]
    except (KeyError, IndexError, TypeError):
        return None
    games = runes.get("n") or 0
    if not games or not chosen.get("pri"):
        return None
    return RunePage(primary_tree, chosen["pri"], secondary_tree, chosen.get("sec") or [],
                    chosen.get("mod") or [], games, (runes.get("wr") or 0) / 100,
                    games / total if total else 0, label)


def _unique(options: list, key) -> list:
    """Tira repetidas (a primeira fica) e corta em MAX_OPTIONS."""
    seen, result = set(), []
    for option in options:
        if option is not None and key(option) not in seen:
            seen.add(key(option))
            result.append(option)
    return result[:MAX_OPTIONS]


def _same_items(option: Option):
    return tuple(sorted(option.ids))


def _same_runes(page: RunePage):
    return frozenset(page.primary), frozenset(page.secondary)  # fragmentos e ordem nao contam


def _general_build(opgg: dict, extra: dict) -> Build:
    """OP.GG (a mais jogada de cada parte) + alternativas do Lolalytics."""
    build = _stats(Build(), opgg.get("summary"))
    build.starters = _unique([_option(opgg.get("starter_items"))]
                             + _lolalytics_options(extra.get("startSet")), _same_items)
    build.boots = _unique([_option(opgg.get("boots"))]
                          + _lolalytics_options(extra.get("boots"), IGNORED_BOOTS), _same_items)
    build.core = [o for o in [_option(opgg.get("core_items"))] if o]
    build.item_slots = [_lolalytics_options(extra.get(f"item{n}")) for n in (1, 2, 3)] + [
        _options(opgg.get(slot)) for slot in ("fourth_items", "fifth_items", "sixth_items")]
    build.spells = _unique([_option(opgg.get("summoner_spells"))]
                           + _lolalytics_options(extra.get("spells")), _same_items)
    build.skill_order = _option(opgg.get("skills"), "order")
    build.skill_priority = _option(opgg.get("skill_masteries"))

    total = (extra.get("header") or {}).get("n") or extra.get("n") or 0
    summary = extra.get("summary") or {}
    build.runes = _unique([
        _opgg_page(opgg.get("runes"), "Mais jogada · OP.GG"),
        _lolalytics_page(summary.get("pick"), total, "Mais jogada · Lolalytics"),
        _lolalytics_page(summary.get("win"), total, "Maior vitória · Lolalytics"),
    ], _same_runes)
    return build


def _matchup_build(data: dict) -> Build:
    build = _stats(Build(), data.get("summary"))
    build.starters = _options(data.get("starter_items"))
    build.boots = _options(data.get("boots"))
    build.core = _options(data.get("core_items"))
    slots = sorted(data.get("single_items") or [], key=lambda s: s.get("depth") or 0)
    # Do 5o item em diante o confronto tem poucas partidas: slot sem amostra fica de fora.
    build.item_slots = [[o for o in _options(slot.get("items")) if o.games >= MIN_GAMES] for slot in slots]
    build.spells = _options(data.get("summoner_spells"))
    build.skill_order = next(iter(_options(data.get("skills"), "order")), None)
    build.skill_priority = next(iter(_options(data.get("skill_masteries"))), None)
    build.runes = _top([p for p in map(_opgg_page, data.get("runes") or []) if p])
    return build


# --- Busca -------------------------------------------------------------------

class BuildAdvisor:
    def __init__(self, mcp: OpggMcpClient):
        self.mcp = mcp
        self._cache: dict[tuple, tuple[float, object]] = {}
        self._locks: dict[tuple, threading.Lock] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _cached(self, key: tuple, fetch):
        with self._lock:
            key_lock = self._locks.setdefault(key, threading.Lock())
        with key_lock:  # duas abas pedindo a mesma coisa: uma chamada so'
            cached = self._cache.get(key)
            if cached is None or time.time() - cached[0] > BUILD_CACHE_SECONDS:
                cached = (time.time(), fetch())
                self._cache[key] = cached
            return cached[1]

    def build(self, champion: Champion, position: str) -> Build:
        return self._cached(("build", champion.id, position), lambda: self._fetch(champion, position))

    def matchup(self, champion: Champion, enemy: Champion, position: str) -> Matchup:
        return self._cached(("matchup", champion.id, enemy.id, position),
                            lambda: self._fetch_matchup(champion, enemy, position))

    def _fetch(self, champion: Champion, position: str) -> Build:
        extra_future = self._executor.submit(lolalytics.build, champion, position)
        result = self.mcp.call_tool("lol_get_champion_analysis", {
            "champion": champion.mcp_name,
            "position": position,
            "game_mode": "ranked",
            "desired_output_fields": FIELDS,
        })
        try:
            extra = extra_future.result()
        except lolalytics.LolalyticsError as exc:
            print(f"[Enzo] Lolalytics sem build, so' com o OP.GG: {exc}")
            extra = {}
        return _general_build(result.get("data") or {}, extra)

    def _fetch_matchup(self, champion: Champion, enemy: Champion, position: str) -> Matchup:
        # Mesmos argumentos de CounterAdvisor.matchup_tip: a chamada fica no cache pros dois.
        guide = self.mcp.call_tool("lol_get_lane_matchup_guide", {
            "my_champion": champion.mcp_name,
            "opponent_champion": enemy.mcp_name,
            "position": position,
        })
        data = guide.get("data") or {}
        versus = next((r for r in data.get("counters") or [] if r.get("champion_id") == enemy.id), None)
        games = (versus or {}).get("play") or 0
        return Matchup(
            build=_matchup_build(data),
            games=games,
            win_rate=versus["win"] / games if games else None,
            tip=data.get("opponent_champion_tip") or None,
            play_style=data.get("recommended_play_style") or None,
            lane_advantage=data.get("lane_advantage_champion") or None,
            solo_kill_advantage=data.get("lane_solo_kill_advantage_champion") or None,
        )
