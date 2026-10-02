"""Lista de campeoes (via MCP do OP.GG) e identificacao de nomes no texto falado."""

import difflib
import re
from dataclasses import dataclass
from functools import lru_cache

from src.core.text import normalize
from src.lol.opgg_mcp import OpggMcpClient

# Ids acima disso sao variantes de modos especiais (ex: 60020 "Jade_Nunu").
MAX_REGULAR_CHAMPION_ID = 10000
FUZZY_THRESHOLD = 0.75
# Nomes que tambem sao palavras comuns ("eu vi"): o interpretador local ignora.
COMMON_WORDS = {"vi"}

# Como o Whisper costuma transcrever alguns nomes falados em portugues.
SPOKEN_ALIASES = {
    "mundo": "Dr. Mundo",
    "nunu": "Nunu & Willump",
    "renata": "Renata Glasc",
    "yi": "Master Yi",
    "master": "Master Yi",
    "tf": "Twisted Fate",
    "mf": "Miss Fortune",
    "asol": "Aurelion Sol",
    "kasante": "K'Sante",
    "keisante": "K'Sante",
    "voli": "Volibear",
    "morde": "Mordekaiser",
    "gp": "Gangplank",
    "cho": "Cho'Gath",
    "chogat": "Cho'Gath",
    "malfite": "Malphite",
    "malfaite": "Malphite",
    "ione": "Yone",
    "vlad": "Vladimir",
    "kata": "Katarina",
    "cait": "Caitlyn",
    "ez": "Ezreal",
    "j4": "Jarvan IV",
    "lee": "Lee Sin",
    "xin": "Xin Zhao",
    "trynda": "Tryndamere",
    "heca": "Hecarim",
    "blitz": "Blitzcrank",
    # "contra a Akali": o artigo engole o "A" ("K'Ali", "Kai'Li", "K'A'L'Y")
    "kali": "Akali",
    "kaili": "Akali",
    "kaly": "Akali",
}


@dataclass(frozen=True)
class Champion:
    id: int
    name: str

    @property
    def mcp_name(self) -> str:
        """Formato UPPER_SNAKE_CASE que o MCP espera (ex: "K'Sante" -> KSANTE,
        "Dr. Mundo" -> DR_MUNDO, "Nunu & Willump" -> NUNU_WILLUMP)."""
        cleaned = re.sub(r"['.]", "", self.name).replace("&", " ")
        return "_".join(cleaned.upper().split())


def _compact(text: str) -> str:
    """Remove tudo que nao e' letra/numero: "Cho'Gath" -> "chogath"."""
    return re.sub(r"[^a-z0-9]", "", normalize(text))


@lru_cache(maxsize=1)
def list_champions(client: OpggMcpClient) -> tuple[Champion, ...]:
    result = client.call_tool(
        "lol_list_champions",
        {"desired_output_fields": ["data.champions[].{champion_id,name}"]},
    )
    return tuple(
        Champion(c["champion_id"], c["name"])
        for c in result["data"]["champions"]
        if c["champion_id"] < MAX_REGULAR_CHAMPION_ID
    )


def by_id(client: OpggMcpClient) -> dict[int, Champion]:
    return {c.id: c for c in list_champions(client)}


def by_name(client: OpggMcpClient, name: str) -> Champion | None:
    target = _compact(name)
    return next((c for c in list_champions(client) if _compact(c.name) == target), None)


def find_in_text(client: OpggMcpClient, text: str, fuzzy: bool = True) -> Champion | None:
    """Acha o campeao citado no texto, tolerando erros de transcricao.
    Compara janelas de 1 a 3 palavras contra os nomes (sem espacos/pontuacao).
    fuzzy=False aceita so' nome exato ou apelido conhecido (sem chute)."""
    champions = list_champions(client)
    lookup = {_compact(c.name): c for c in champions}
    for alias, name in SPOKEN_ALIASES.items():
        lookup.setdefault(alias, by_name(client, name))

    words = [_compact(w) for w in normalize(text).split()]
    words = [w for w in words if w]
    best, best_score = None, 0.0
    for size in (3, 2, 1):
        for i in range(len(words) - size + 1):
            candidate = "".join(words[i:i + size])
            if candidate in lookup and lookup[candidate] is not None:
                return lookup[candidate]
            if not fuzzy or len(candidate) < 3:
                continue
            for key, champion in lookup.items():
                if champion is None:
                    continue
                score = difflib.SequenceMatcher(None, candidate, key).ratio()
                if score > best_score:
                    best, best_score = champion, score
    return best if best_score >= FUZZY_THRESHOLD else None


def find_all_in_text(client: OpggMcpClient, text: str) -> list[Champion]:
    """Todos os campeoes citados pelo nome exato ou apelido, na ordem da frase
    ("meu time e' naafiri, vlad e jinx"). Sem chute: serve pro interpretador local."""
    lookup = {_compact(c.name): c for c in list_champions(client)}
    for alias, name in SPOKEN_ALIASES.items():
        lookup.setdefault(alias, by_name(client, name))
    for word in COMMON_WORDS:
        lookup.pop(word, None)

    words = [w for w in (_compact(w) for w in normalize(text).split()) if w]
    found, i = [], 0
    while i < len(words):
        for size in (3, 2, 1):
            champion = lookup.get("".join(words[i:i + size]))
            if champion and len(words[i:i + size]) == size:
                if champion not in found:
                    found.append(champion)
                i += size
                break
        else:
            i += 1
    return found
