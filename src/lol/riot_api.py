"""Chamadas a API oficial da Riot (chave em RIOT_API_KEY no .env)."""

import httpx

from src.core import config


class RiotApiError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None):
    if not config.RIOT_API_KEY:
        raise RiotApiError("RIOT_API_KEY nao configurada no .env")
    response = httpx.get(
        url, params=params, headers={"X-Riot-Token": config.RIOT_API_KEY}, timeout=20
    )
    if response.status_code == 403:
        raise RiotApiError("Chave da Riot recusada (403). Chaves de dev expiram a cada 24h.")
    if response.status_code != 200:
        raise RiotApiError(f"Riot API {response.status_code}: {response.text[:200]}")
    return response.json()


def get_puuid(game_name: str, tag_line: str) -> str:
    data = _get(
        f"https://{config.RIOT_REGIONAL_ROUTE}.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    )
    return data["puuid"]


def get_top_masteries(puuid: str, count: int = 10) -> list[dict]:
    """Lista de {championId, championPoints, championLevel, ...}, maior maestria primeiro."""
    return _get(
        f"https://{config.RIOT_PLATFORM}.api.riotgames.com"
        f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top",
        params={"count": count},
    )
