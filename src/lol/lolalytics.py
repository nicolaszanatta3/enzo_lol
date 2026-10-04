"""Estatisticas do lolalytics.com pela API JSON que o proprio site usa
(a1.lolalytics.com/mega), sem chave nem cota.

Todas as respostas usam o id numerico da Riot (o mesmo do OP.GG), entao
nao precisa converter nomes. Endpoints usados (parametro `ep`):
  - "list": tier list de uma rota, `cid` = {id: {rank, tier, wr, pr, br, games...}};
  - "counter": desempenho de `c` contra cada adversario da rota, `counters` =
    [{cid, vsWr, n...}] com vsWr = winrate de `c` CONTRA o adversario;
  - "build-team": sinergia de `c` com os aliados de cada rota, `team` =
    {rota: [[id, wr, d1, d2, pr, n], ...]} (colunas em `team_h`);
  - "build-full": build de `c` na rota, com varias opcoes de cada parte
    (interpretada em src/lol/builds.py).
Percentuais vem de 0 a 100; aqui viram fracoes de 0 a 1.
"""

import re
from dataclasses import dataclass

import httpx

from src.core import config
from src.core.cache import HOUR, cache, key
from src.lol.champions import Champion

API_URL = "https://a1.lolalytics.com/mega/"
# Rotas do Enzo (padrao OP.GG) -> parametro `lane` do Lolalytics.
LANES = {"top": "top", "jungle": "jungle", "mid": "middle", "adc": "bottom", "support": "support"}
POSITION_BY_LANE = {lane: position for position, lane in LANES.items()}
# Slug normalmente e' o nome so' com letras minusculas; excecoes:
SLUG_EXCEPTIONS = {"Nunu & Willump": "nunu", "Renata Glasc": "renata"}
# Tier 1 = S+ ... 15 = D-; 0 = sem tier (pouca amostra ou fora da rota).
SYNERGY_DAYS = 30  # parametro `patch` aceita 7, 14 ou 30 (dias); sem ele, patch atual
# Arvores de runa na ordem dos indices `page.pri`/`page.sec` do "build-full".
RUNE_TREES = [8000, 8100, 8200, 8400, 8300]  # Precisao, Dominacao, Feiticaria, Determinacao, Inspiracao
TIER_LABELS = ["-", "S+", "S", "S-", "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"]


class LolalyticsError(RuntimeError):
    pass


@dataclass
class LaneStats:
    tier: int  # 1 (S+) a 15 (D-); 0 = sem tier
    win_rate: float
    pick_rate: float
    ban_rate: float
    games: int


@dataclass
class Synergy:
    games: int
    win_rate: float  # da dupla junta
    delta: float  # "Normalised Synergy Delta": quanto a dupla ganha alem do esperado pelos dois


def slug(champion: Champion) -> str:
    return SLUG_EXCEPTIONS.get(champion.name) or re.sub(r"[^a-z]", "", champion.name.lower())


CACHE_TTL = 6 * HOUR


def _get(endpoint: str, **params) -> dict:
    params = {"ep": endpoint, "v": 1, "tier": config.LOLALYTICS_TIER,
              "queue": "ranked", "region": "all", **params}
    return cache.get(key("lolalytics", params), lambda: _fetch(endpoint, params), ttl=CACHE_TTL)


def _fetch(endpoint: str, params: dict) -> dict:
    try:
        response = httpx.get(API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LolalyticsError(f"{endpoint} {params.get('c', '')}: {exc}") from exc
    if not data.get("response", {}).get("valid", True):
        raise LolalyticsError(f"{endpoint}: endpoint invalido (API mudou?)")
    return data


def counters(champion: Champion, position: str) -> dict[int, tuple[int, float]]:
    """Desempenho de `champion` contra cada adversario da rota:
    {id do adversario: (partidas, winrate de `champion` de 0 a 1)}."""
    data = _get("counter", c=slug(champion), lane=LANES[position])
    result = {row["cid"]: (row["n"], row["vsWr"] / 100) for row in data.get("counters") or []}
    if not result:
        raise LolalyticsError(f"{champion.name}: nenhum counter no {position}")
    return result


def lane_stats(position: str) -> dict[int, LaneStats]:
    """Tier list da rota: {id do campeao: LaneStats} (inclui quem nao tem tier)."""
    data = _get("list", lane=LANES[position])
    return {
        int(cid): LaneStats(row["tier"], row["wr"] / 100, row["pr"] / 100, row["br"] / 100, row["games"])
        for cid, row in (data.get("cid") or {}).items()
    }


def synergies(champion: Champion, position: str) -> dict[str, dict[int, Synergy]]:
    """Sinergia de `champion` (jogando em `position`) com os aliados de cada
    rota: {rota do aliado: {id do aliado: Synergy}}. Usa os ultimos
    SYNERGY_DAYS dias em vez da patch atual: dupla muda pouco de uma patch pra
    outra, e so' a patch atual da' poucas centenas de partidas por dupla."""
    data = _get("build-team", c=slug(champion), lane=LANES[position], patch=SYNERGY_DAYS)
    columns = data.get("team_h") or []
    result: dict[str, dict[int, Synergy]] = {}
    for lane, rows in (data.get("team") or {}).items():
        by_id = {}
        for row in rows:
            values = dict(zip(columns, row))
            by_id[values["id"]] = Synergy(values["n"], values["wr"] / 100, values["d2"] / 100)
        result[POSITION_BY_LANE.get(lane, lane)] = by_id
    return result


def build(champion: Champion, position: str) -> dict:
    """Resposta crua do "build-full". Listas no formato [ids, wr, pr, n, ...]
    (ids juntos por "_" quando sao varios; wr e pr de 0 a 100):
      startSet, boots, spells, item1..item5; e em summary.pick / summary.win a
    pagina de runas mais jogada / que mais vence ({wr, n, page, set})."""
    data = _get("build-full", c=slug(champion), lane=LANES[position])
    if not data.get("summary"):
        raise LolalyticsError(f"{champion.name}: sem build no {position}")
    return data
