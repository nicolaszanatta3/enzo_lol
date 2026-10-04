"""Cache em disco das respostas das APIs (OP.GG, Lolalytics, Data Dragon, Riot).

Estatistica muda pouco ao longo do dia, entao cada resposta fica salva num
SQLite (sobrevive a reiniciar o site e e' compartilhado com a voz) e volta assim:
  - nova (menos de `ttl`): direto do cache;
  - velha (menos de `max_age`): devolve na hora e atualiza em segundo plano;
  - sem nada, ou velha demais: busca agora. Quem pedir a mesma coisa ao mesmo
    tempo espera essa busca em vez de repetir a chamada.
Se a busca falhar e houver qualquer copia (mesmo velhissima), usa a copia.
So' guarda valores que viram JSON (as respostas cruas, antes de interpretar).
"""

import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from src.core import config

DB_PATH = config.ASSETS_DIR / "cache" / "api.sqlite3"
MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
MAX_STALE = 7 * DAY


class DiskCache:
    def __init__(self, path=DB_PATH):
        self._path = path
        self._db: sqlite3.Connection | None = None
        self._memory: dict[str, tuple[float, Any]] = {}
        self._db_lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        self._refreshing: set[str] = set()
        self._lock = threading.Lock()
        self._background = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cache")

    def get(self, key: str, fetch: Callable[[], Any], ttl: float, max_age: float = MAX_STALE) -> Any:
        entry = self._read(key)
        if entry and time.time() - entry[0] < ttl:
            return entry[1]
        if entry and time.time() - entry[0] < max_age:
            self._refresh_later(key, fetch)
            return entry[1]
        with self._key_lock(key):
            entry = self._read(key)  # outra thread pode ter buscado enquanto esta esperava
            if entry and time.time() - entry[0] < ttl:
                return entry[1]
            try:
                return self._store(key, fetch())
            except Exception:
                if entry:
                    return entry[1]
                raise

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def _refresh_later(self, key: str, fetch: Callable[[], Any]) -> None:
        with self._lock:
            if key in self._refreshing:
                return
            self._refreshing.add(key)

        def refresh():
            try:
                with self._key_lock(key):
                    self._store(key, fetch())
            except Exception as exc:
                print(f"[Enzo] Nao atualizei o cache de {key[:80]}: {exc}")
            finally:
                with self._lock:
                    self._refreshing.discard(key)

        self._background.submit(refresh)

    # --- Armazenamento -----------------------------------------------------

    def _connection(self) -> sqlite3.Connection:
        if self._db is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self._path, check_same_thread=False, timeout=10)
            self._db.execute("PRAGMA journal_mode=WAL")  # voz e site podem usar ao mesmo tempo
            self._db.execute("CREATE TABLE IF NOT EXISTS entries "
                             "(key TEXT PRIMARY KEY, saved_at REAL NOT NULL, value TEXT NOT NULL)")
            self._db.commit()
        return self._db

    def _read(self, key: str) -> tuple[float, Any] | None:
        entry = self._memory.get(key)
        if entry is not None:
            return entry
        with self._db_lock:
            row = self._connection().execute(
                "SELECT saved_at, value FROM entries WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        entry = (row[0], json.loads(row[1]))
        self._memory[key] = entry
        return entry

    def _store(self, key: str, value: Any) -> Any:
        saved_at = time.time()
        encoded = json.dumps(value, ensure_ascii=False)
        with self._db_lock:
            db = self._connection()
            db.execute("INSERT OR REPLACE INTO entries VALUES (?, ?, ?)", (key, saved_at, encoded))
            db.commit()
        self._memory[key] = (saved_at, value)
        return value


cache = DiskCache()


def key(*parts) -> str:
    """Chave estavel a partir de nomes e parametros (dicts em qualquer ordem)."""
    return "|".join(json.dumps(p, sort_keys=True, ensure_ascii=False) if isinstance(p, (dict, list)) else str(p)
                    for p in parts)
