"""Dicas de confronto do OP.GG (em ingles) traduzidas por LLM, com cache em disco.

Usado pela voz (dica falada depois dos counters) e pelo site (modal do confronto):
os dois compartilham as traducoes, pra nao gastar cota de LLM com o mesmo confronto.
"""

import json
import threading

from src.ai import llm
from src.core import config
from src.lol.champions import Champion

SYSTEM_PROMPT = (
    "Traduza a dica de League of Legends para português do Brasil, com acentuação "
    "correta, em no máximo duas frases curtas, naturais para falar em voz alta. "
    "As marcações (X) são habilidades do adversário e [X] do campeão do jogador: "
    "troque por 'o Q', 'o E', 'a ultimate' (R) ou 'a passiva' (P). "
    "Não deixe colchetes nem parênteses. Só a dica, sem aspas."
)
CACHE_PATH = config.ASSETS_DIR / "cache" / "dicas_traduzidas.json"


class TipTranslator:
    def __init__(self):
        self._lock = threading.Lock()
        try:
            self._cache: dict[str, str] = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self._cache = {}

    def translate(self, mine: Champion, enemy: Champion, position: str, tip: str) -> str | None:
        """Dica em portugues, ou None se nenhum LLM respondeu."""
        key = f"{mine.name}|{enemy.name}|{position}"
        translated = self._cache.get(key)
        if translated is None:
            try:
                translated = llm.generate_text(tip, SYSTEM_PROMPT)
            except llm.LLMError:
                return None
            self._save(key, translated)
        return translated

    def _save(self, key: str, translated: str) -> None:
        with self._lock:
            self._cache[key] = translated
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps(self._cache, ensure_ascii=False, indent=1), encoding="utf-8")
