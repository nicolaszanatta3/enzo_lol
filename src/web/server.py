"""Site do Enzo: escolhe o campeao e a rota e ve counters, bans, build e runas.

Rodar (a partir da raiz do projeto):
    python -m src.web.server          # abre http://127.0.0.1:8000 no navegador

O frontend (web/) e' compilado com `npm run build` e servido daqui. Pra
mexer no visual com recarga automatica: `npm run dev` dentro de web/ (o Vite
repassa /api pra ca').
"""

import threading
import webbrowser
from contextlib import asynccontextmanager
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.core import config
from src.lol import champions, lolalytics
from src.lol.advisor import CounterAdvisor, CounterPick, Source, personal_summary
from src.lol.builds import Build, BuildAdvisor, Option
from src.lol.champions import SPOKEN_ALIASES, Champion
from src.lol.draft import DraftAdvisor
from src.lol.meta import POSITIONS, MetaAdvisor
from src.lol.profiles import ProfileStore
from src.web.ddragon import SHARD_ROWS, DataDragon

HOST, PORT = "127.0.0.1", 8000
DIST_DIR = config.PROJECT_ROOT / "web" / "dist"
COUNTERS_SHOWN = 12
BANS_SHOWN = 8

Position = Literal["top", "jungle", "mid", "adc", "support"]

counters_advisor = CounterAdvisor()
mcp = counters_advisor.mcp
meta = MetaAdvisor(mcp)
draft = DraftAdvisor(counters_advisor, meta, ProfileStore(mcp))
builds = BuildAdvisor(mcp)
ddragon = DataDragon()



def _warm_up() -> None:
    """Adianta o que toda pergunta usa; se falhar, cada rota tenta de novo."""
    for step in (ddragon.data, lambda: champions.list_champions(mcp),
                 lambda: meta.lane(config.MAIN_POSITION), counters_advisor.player_pool):
        try:
            step()
        except Exception as exc:
            print(f"[Enzo] Pre-carregamento falhou ({exc}); tento de novo quando pedirem.")


@asynccontextmanager
async def _lifespan(_: FastAPI):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="Enzo", lifespan=_lifespan)


def _fail(what: str, exc: Exception) -> HTTPException:
    print(f"[Enzo] {what}: {exc!r}")
    return HTTPException(502, f"Não consegui buscar {what} agora. Tenta de novo em instantes.")


def _champion(champion_id: int) -> Champion:
    champion = champions.by_id(mcp).get(champion_id)
    if champion is None:
        raise HTTPException(404, "Campeão não encontrado.")
    return champion


def _champion_ref(champion: Champion) -> dict:
    data = ddragon.data()
    name = data.champions.get(champion.id, {}).get("name") or champion.name
    return {"id": champion.id, "name": name, "icon": data.champion_icon(champion.id)}


# --- Campeoes ----------------------------------------------------------------

@app.get("/api/champions")
def list_champions() -> list[dict]:
    try:
        data = ddragon.data()
        roster = champions.list_champions(mcp)
    except Exception as exc:
        raise _fail("a lista de campeões", exc)
    try:
        lanes = {c.id: meta.role_rates(c) for c in roster}
    except Exception as exc:  # sem a rota principal o site ainda funciona
        print(f"[Enzo] Rotas dos campeoes indisponiveis: {exc!r}")
        lanes = {}
    aliases: dict[str, list[str]] = {}
    for alias, name in SPOKEN_ALIASES.items():
        aliases.setdefault(name, []).append(alias)

    result = []
    for champion in roster:
        if champion.id not in data.champions:
            continue
        rates = lanes.get(champion.id) or {}
        result.append({
            **_champion_ref(champion),
            "splash": data.champion_splash(champion.id),
            "aliases": aliases.get(champion.name, []) + [champion.name],
            "lanes": {p: round(rates.get(p, 0), 4) for p in POSITIONS},
        })
    return sorted(result, key=lambda c: c["name"])


# --- Counters ------------------------------------------------------------------

def _source(source: Source | None) -> dict | None:
    # Source.win_rate e' do adversario contra o campeao escolhido; o site mostra o do jogador.
    return {"myWinRate": 1 - source.win_rate, "games": source.games} if source else None


def _counter_row(pick: CounterPick) -> dict:
    return {
        **_champion_ref(pick.champion),
        "myWinRate": 1 - pick.win_rate,
        "games": sum(s.games for s in pick.sources),
        "opgg": _source(pick.opgg),
        "lolalytics": _source(pick.lolalytics),
        "pool": personal_summary(pick.pool) if pick.pool else None,
    }


@app.get("/api/counters/{champion_id}/{position}")
def get_counters(champion_id: int, position: Position) -> dict:
    champion = _champion(champion_id)
    try:
        picks = counters_advisor.counters(champion, position)  # do que mais ganha dele pro que mais perde
    except Exception as exc:
        raise _fail(f"os counters de {champion.name}", exc)
    return {
        "against": [_counter_row(p) for p in picks if p.win_rate > 0.5][:COUNTERS_SHOWN],
        "favorable": [_counter_row(p) for p in reversed(picks) if p.win_rate < 0.5][:COUNTERS_SHOWN],
        "tier": config.LOLALYTICS_TIER,
    }


# --- Bans --------------------------------------------------------------------

@app.get("/api/bans/{champion_id}/{position}")
def get_bans(champion_id: int, position: Position) -> list[dict]:
    champion = _champion(champion_id)
    try:
        targets = draft.bans_against(champion, position)
    except Exception as exc:
        raise _fail(f"os bans pra {champion.name}", exc)
    return [{
        **_champion_ref(t.champion),
        "splash": ddragon.data().champion_splash(t.champion.id),
        "myWinRate": 1 - t.win_rate,
        "pickRate": t.pick_rate,
        "threat": t.threat * 1000,
        "games": sum(s.games for s in t.counter.sources) if t.counter else 0,
    } for t in targets[:BANS_SHOWN]]


# --- Build e runas -----------------------------------------------------------

def _stats(option: Option) -> dict:
    return {"winRate": option.win_rate, "games": option.games, "pickRate": option.pick_rate}


def _items(option: Option | None) -> dict | None:
    if option is None:
        return None
    items = ddragon.data().items
    return {"items": [{"id": i, **items.get(i, {"name": f"Item {i}", "icon": None, "gold": 0, "description": ""})}
                      for i in option.ids], **_stats(option)}


def _rune(rune_id: int, selected: bool) -> dict:
    rune = ddragon.data().runes.get(rune_id, {"name": f"Runa {rune_id}", "icon": None, "description": ""})
    return {"id": rune_id, **rune, "selected": selected}


def _tree(tree_id: int, chosen: list[int], skip_keystone: bool) -> dict | None:
    tree = ddragon.data().trees.get(tree_id)
    if tree is None:
        return None
    slots = tree["slots"][1:] if skip_keystone else tree["slots"]
    return {
        "tree": {k: tree[k] for k in ("id", "key", "name", "icon")},
        "rows": [[_rune(r, r in chosen) for r in slot] for slot in slots],
    }


def _runes(build: Build) -> dict | None:
    runes = build.runes
    if runes is None:
        return None
    return {
        "primary": _tree(runes.primary_tree, runes.primary, skip_keystone=False),
        "secondary": _tree(runes.secondary_tree, runes.secondary, skip_keystone=True),
        "shards": [[_rune(r, i < len(runes.shards) and runes.shards[i] == r) for r in row]
                   for i, row in enumerate(SHARD_ROWS)],
        "winRate": runes.win_rate, "games": runes.games, "pickRate": runes.pick_rate,
    }


def _lolalytics_tier(champion: Champion, position: str) -> str | None:
    try:
        entry = meta.lane(position).get(champion.id)
    except Exception:
        return None
    if entry and entry.lolalytics and entry.lolalytics.tier:
        return lolalytics.TIER_LABELS[entry.lolalytics.tier]
    return None


@app.get("/api/build/{champion_id}/{position}")
def get_build(champion_id: int, position: Position) -> dict:
    champion = _champion(champion_id)
    try:
        build = builds.build(champion, position)
        data = ddragon.data()
        abilities = ddragon.champion_spells(champion.id)
    except Exception as exc:
        raise _fail(f"a build de {champion.name}", exc)

    spells = None
    if build.spells:
        spells = {"spells": [{"id": s, **data.spells.get(s, {"name": f"Feitiço {s}", "icon": None,
                                                              "description": ""})}
                             for s in build.spells.ids], **_stats(build.spells)}
    skills = None
    if build.skill_order or build.skill_priority:
        reference = build.skill_order or build.skill_priority
        skills = {
            "abilities": abilities,
            "order": build.skill_order.ids if build.skill_order else [],
            "priority": build.skill_priority.ids if build.skill_priority else [],
            **_stats(reference),
        }
    return {
        "stats": {
            "tier": build.tier, "rank": build.rank, "winRate": build.win_rate,
            "pickRate": build.pick_rate, "banRate": build.ban_rate, "kda": build.kda,
            "games": build.games, "lolalyticsTier": _lolalytics_tier(champion, position),
        },
        "starter": _items(build.starter),
        "boots": _items(build.boots),
        "core": _items(build.core),
        "situational": [
            {"slot": slot, "options": [_items(o) for o in options]}
            for slot, options in (("4º item", build.fourth), ("5º item", build.fifth), ("6º item", build.sixth))
            if options
        ],
        "spells": spells,
        "skills": skills,
        "runes": _runes(build),
    }


if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="site")


def run() -> None:
    if not DIST_DIR.exists():
        print("Frontend nao compilado: rode `npm install` e `npm run build` dentro de web/.")
    threading.Timer(1.5, webbrowser.open, args=(f"http://{HOST}:{PORT}",)).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    run()
