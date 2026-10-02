"""Nomes em portugues e imagens do jogo, pelo Data Dragon da Riot (CDN publica).

  - campeoes, itens, feiticos e arvores de runas: ddragon.leagueoflegends.com;
  - fragmentos de atributo (5001, 5005...) nao estao no Data Dragon: vem do
    CommunityDragon (perks.json), que tem todas as runas.
Tudo e' baixado uma vez por execucao (na versao mais nova do jogo).
"""

import re
import threading
from dataclasses import dataclass, field

import httpx

DDRAGON = "https://ddragon.leagueoflegends.com"
CDRAGON = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global"
LANG = "pt_BR"

# Fileiras de fragmentos da season atual: ataque, flex, defesa.
SHARD_ROWS = [[5008, 5005, 5007], [5008, 5010, 5001], [5011, 5013, 5001]]


def _plain(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html or "")
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


@dataclass
class StaticData:
    version: str
    champions: dict[int, dict] = field(default_factory=dict)  # id numerico -> {key, name}
    items: dict[int, dict] = field(default_factory=dict)
    spells: dict[int, dict] = field(default_factory=dict)
    trees: dict[int, dict] = field(default_factory=dict)
    runes: dict[int, dict] = field(default_factory=dict)  # inclui fragmentos

    def champion_icon(self, champion_id: int) -> str | None:
        champion = self.champions.get(champion_id)
        if not champion:
            return None
        return f"{DDRAGON}/cdn/{self.version}/img/champion/{champion['key']}.png"

    def champion_splash(self, champion_id: int) -> str | None:
        champion = self.champions.get(champion_id)
        return f"{DDRAGON}/cdn/img/champion/splash/{champion['key']}_0.jpg" if champion else None


class DataDragon:
    def __init__(self):
        self._http = httpx.Client(timeout=20)
        self._data: StaticData | None = None
        self._spells_by_champion: dict[int, list[dict]] = {}
        self._lock = threading.Lock()

    def _get(self, url: str):
        response = self._http.get(url)
        response.raise_for_status()
        return response.json()

    def data(self) -> StaticData:
        with self._lock:
            if self._data is None:
                self._data = self._load()
            return self._data

    def _load(self) -> StaticData:
        version = self._get(f"{DDRAGON}/api/versions.json")[0]
        base = f"{DDRAGON}/cdn/{version}"
        data = StaticData(version)

        for champion in self._get(f"{base}/data/{LANG}/champion.json")["data"].values():
            data.champions[int(champion["key"])] = {"key": champion["id"], "name": champion["name"]}

        for item_id, item in self._get(f"{base}/data/{LANG}/item.json")["data"].items():
            data.items[int(item_id)] = {
                "name": item["name"],
                "icon": f"{base}/img/item/{item['image']['full']}",
                "gold": item["gold"]["total"],
                "description": item.get("plaintext") or _plain(item.get("description", ""))[:220],
            }

        for spell in self._get(f"{base}/data/{LANG}/summoner.json")["data"].values():
            data.spells[int(spell["key"])] = {
                "name": spell["name"],
                "icon": f"{base}/img/spell/{spell['image']['full']}",
                "description": _plain(spell["description"]),
            }

        for tree in self._get(f"{base}/data/{LANG}/runesReforged.json"):
            data.trees[tree["id"]] = {
                "id": tree["id"],
                "key": tree["key"],
                "name": tree["name"],
                "icon": f"{DDRAGON}/cdn/img/{tree['icon']}",
                "slots": [[rune["id"] for rune in slot["runes"]] for slot in tree["slots"]],
            }
            for slot in tree["slots"]:
                for rune in slot["runes"]:
                    data.runes[rune["id"]] = {
                        "name": rune["name"],
                        "icon": f"{DDRAGON}/cdn/img/{rune['icon']}",
                        "description": _plain(rune["shortDesc"]),
                    }

        for perk in self._get(f"{CDRAGON}/{LANG.lower()}/v1/perks.json"):
            if perk["id"] in data.runes or not 5000 < perk["id"] < 5100:
                continue
            icon = perk["iconPath"].lower().replace("/lol-game-data/assets/", f"{CDRAGON}/default/")
            data.runes[perk["id"]] = {"name": perk["name"], "icon": icon,
                                      "description": _plain(perk["shortDesc"])}
        return data

    def champion_spells(self, champion_id: int) -> list[dict]:
        """Passiva + Q, W, E, R do campeao (nome e icone)."""
        cached = self._spells_by_champion.get(champion_id)
        if cached is not None:
            return cached
        data = self.data()
        key = data.champions[champion_id]["key"]
        base = f"{DDRAGON}/cdn/{data.version}"
        detail = self._get(f"{base}/data/{LANG}/champion/{key}.json")["data"][key]
        spells = [{"key": "P", "name": detail["passive"]["name"],
                   "icon": f"{base}/img/passive/{detail['passive']['image']['full']}"}]
        spells += [{"key": letter, "name": spell["name"], "icon": f"{base}/img/spell/{spell['image']['full']}"}
                   for letter, spell in zip("QWER", detail["spells"])]
        self._spells_by_champion[champion_id] = spells
        return spells
