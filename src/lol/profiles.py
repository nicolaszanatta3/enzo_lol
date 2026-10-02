"""Perfil de cada campeao pra analisar composicao: classes e tipo de dano.

  - classes (tags da Riot: Tank, Fighter, Mage, Assassin, Marksman, Support)
    vem de lol_list_champion_details, 10 campeoes por chamada;
  - tipo de dano (AD, AP ou BOTH) vem de lol_get_champion_analysis, uma
    chamada (~5s) por campeao, na rota principal dele. O rating "magic" dos
    detalhes NAO serve: e' o quanto o kit depende de habilidades (Jax = 7).

Isso quase nunca muda, entao fica salvo em disco; so' campeao novo e' buscado.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

from src.core import config
from src.lol import champions
from src.lol.champions import Champion
from src.lol.opgg_mcp import McpError, OpggMcpClient

CACHE_PATH = config.ASSETS_DIR / "cache" / "perfis_campeoes.json"
DETAILS_BATCH = 10  # maximo da ferramenta
PARALLEL_REQUESTS = 6

# Necessidades de composicao que o Enzo entende.
NEED_CARRY = "carry"
NEED_TANK = "tank"
NEED_AP = "ap"
NEED_AD = "ad"
NEEDS = [NEED_CARRY, NEED_TANK, NEED_AP, NEED_AD]
NEED_LABELS = {
    NEED_CARRY: "carry",
    NEED_TANK: "frontline",
    NEED_AP: "dano mágico",
    NEED_AD: "dano físico",
}


@dataclass
class Profile:
    tags: list[str]
    damage_type: str | None  # "AD", "AP", "BOTH" ou None se o OP.GG nao soube

    @property
    def is_tank(self) -> bool:
        return "Tank" in self.tags

    @property
    def is_carry(self) -> bool:
        """Quem carrega por dano: nada de tanque, nem suporte como classe principal
        (Jax, Fiora, Vladimir e Jinx sim; Garen, Sett, Ornn e Lulu nao)."""
        return bool(self.tags) and not self.is_tank and self.tags[0] != "Support"

    @property
    def deals_ap(self) -> bool:
        return self.damage_type in ("AP", "BOTH")

    @property
    def deals_ad(self) -> bool:
        return self.damage_type in ("AD", "BOTH")

    def fills(self, need: str) -> bool:
        return {
            NEED_CARRY: self.is_carry,
            NEED_TANK: self.is_tank,
            NEED_AP: self.deals_ap,
            NEED_AD: self.deals_ad,
        }[need]


class ProfileStore:
    def __init__(self, mcp: OpggMcpClient):
        self.mcp = mcp
        self._lock = threading.Lock()
        try:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            self._profiles = {int(k): Profile(**v) for k, v in raw.items()}
        except (FileNotFoundError, ValueError, TypeError):
            self._profiles: dict[int, Profile] = {}

    def get(self, champion: Champion) -> Profile | None:
        return self._profiles.get(champion.id)

    def ensure(self, wanted: list[Champion], main_position) -> dict[int, Profile]:
        """Busca (e salva) o perfil de quem ainda nao tem. `main_position(champion)`
        diz em que rota consultar o tipo de dano."""
        missing = [c for c in dict.fromkeys(wanted) if c.id not in self._profiles]
        if missing:
            self._fetch(missing, main_position)
        return {c.id: self._profiles[c.id] for c in wanted if c.id in self._profiles}

    def ensure_all(self, main_position) -> None:
        """Pra rodar no warm_up: a primeira vez leva ~2 min (173 campeoes)."""
        self.ensure(list(champions.list_champions(self.mcp)), main_position)

    def _fetch(self, missing: list[Champion], main_position) -> None:
        batches = [missing[i:i + DETAILS_BATCH] for i in range(0, len(missing), DETAILS_BATCH)]
        with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as executor:
            tag_results = executor.map(self._fetch_tags, batches)
            damage_results = executor.map(lambda c: self._fetch_damage_type(c, main_position(c)), missing)
            tags = {name: t for batch in tag_results for name, t in batch.items()}
            damage = dict(zip(missing, damage_results))

        with self._lock:
            for champion in missing:
                if champion.name in tags:  # sem tags o perfil nao serve; tenta de novo depois
                    self._profiles[champion.id] = Profile(tags[champion.name], damage[champion])
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps(
                {str(k): asdict(v) for k, v in self._profiles.items()}, ensure_ascii=False, indent=1
            ), encoding="utf-8")

    def _fetch_tags(self, batch: list[Champion]) -> dict[str, list[str]]:
        try:
            result = self.mcp.call_tool("lol_list_champion_details", {
                "champions": [c.mcp_name for c in batch],
                "desired_output_fields": ["data.champions[].{name,tags[]}"],
            })
        except McpError as exc:
            print(f"[Enzo] Classes indisponiveis: {exc}")
            return {}
        return {c["name"]: c["tags"] for c in (result.get("data") or {}).get("champions") or []}

    def _fetch_damage_type(self, champion: Champion, position: str | None) -> str | None:
        if position is None:
            return None
        try:
            result = self.mcp.call_tool("lol_get_champion_analysis", {
                "champion": champion.mcp_name,
                "position": position,
                "game_mode": "ranked",
                "desired_output_fields": ["data.damage_type"],
            })
        except McpError as exc:
            print(f"[Enzo] Tipo de dano de {champion.name} indisponivel: {exc}")
            return None
        return (result.get("data") or {}).get("damage_type")
