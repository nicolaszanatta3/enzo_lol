"""Entende o comando falado e decide qual ferramenta do Enzo usar.

Funciona como function calling em UMA chamada: o LLM devolve a acao e os
parametros ja' no formato das APIs (nome oficial do campeao em ingles, rota
no padrao do OP.GG). Chamadas classicas de tools gastariam uma ida e volta a
mais so' pra gerar a resposta final, que aqui e' montada localmente.

Se nenhum LLM responder (sem internet, cota), cai num interpretador local.
"""

import re
from dataclasses import dataclass, field

from src.ai import llm
from src.core import config
from src.core.text import normalize

ACTION_COUNTER = "counter"
ACTION_BAN = "ban"
ACTION_META = "meta"
ACTION_PICK = "pick"
ACTION_UNKNOWN = "unknown"
ACTIONS = [ACTION_COUNTER, ACTION_BAN, ACTION_META, ACTION_PICK, ACTION_UNKNOWN]
POSITIONS = ["top", "jungle", "mid", "adc", "support"]
NEEDS = ["carry", "tank", "ap", "ad"]  # mesmos valores de src/lol/profiles.py

SYSTEM_PROMPT = f"""\
Voce e' o roteador do {config.ASSISTANT_NAME}, assistente de voz de League of Legends.
Recebe a transcricao (Whisper, portugues do Brasil) do que o jogador falou e
escolhe a ferramenta certa.

Nomes de campeao: use sempre o da lista "Campeoes existentes" cujo nome SOA
mais parecido com o transcrito, escrito igual a' lista. A transcricao costuma
errar a grafia ("malfite" = Malphite, "kei sante" = K'Sante, "mundo" = Dr. Mundo,
"ione" = Yone, "caixa" = Kai'Sa, "vlad" = Vladimir). Apostrofos e letras soltas
sao invencao da transcricao: ignore-os e compare o som ("K'A'L'Y" = "kali"). O
artigo antes do nome pode engolir a primeira letra dele: "contra a K'Ali" e
"contra a Kai'Li" = contra a Akali.

Rotas: topo=top, selva/jungle=jungle, meio=mid, bot/atirador=adc, suporte=support.
Campo position = a rota DO JOGADOR, so' se ele disser ("to top", "vou de mid");
senao null.

Ferramentas:
- "counter": enfrenta UM campeao e quer saber o que jogar contra ele, sem
  falar do proprio time ("to contra Malphite, do que eu jogo?").
  enemy_champion = o adversario.
- "ban": quer saber quem banir ("quero jogar de Fizz, o que bano?", "o que
  banir no top?"). my_champion = o campeao que ele quer jogar, se citado.
- "meta": quer saber o que esta forte/bom/roubado/meta numa rota ("o que ta
  bom no top?", "tier list do mid"). position = a rota perguntada.
- "pick": quer saber o que pegar considerando o proprio time ou o que falta
  nele ("meu time e' Naafiri, Vlad, Jinx e Lulu, o que pego?", "meu time nao
  tem carry, to top, o que pego?"). allies = aliados citados, cada um com
  position so' se a rota dele for dita. needs = o que o jogador DISSE que
  falta: carry, tank (tanque/frontline), ap (dano magico), ad (dano fisico).
  enemy_champion = o adversario de rota, se citado.
- "unknown": qualquer outra coisa, inclusive quando nao da pra identificar o
  campeao. Preencha reply com UMA frase curta em portugues do Brasil COM
  ACENTUACAO CORRETA (vai ser lida por uma voz sintetica), com leve deboche.
  Se parecia pergunta de LoL mas o campeao nao existe, peca pra repetir o
  nome; senao, diga que ajuda com counter, ban, meta da rota e pick pro time.
Campos que nao se aplicam: null (ou lista vazia).
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ACTIONS},
        "enemy_champion": {"type": "string", "nullable": True},
        "my_champion": {"type": "string", "nullable": True},
        "position": {"type": "string", "enum": POSITIONS, "nullable": True},
        "allies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "champion": {"type": "string"},
                    "position": {"type": "string", "enum": POSITIONS, "nullable": True},
                },
                "required": ["champion", "position"],
            },
        },
        "needs": {"type": "array", "items": {"type": "string", "enum": NEEDS}},
        "reply": {"type": "string", "nullable": True},
    },
    "required": ["action", "enemy_champion", "my_champion", "position", "allies", "needs", "reply"],
}

POSITION_WORDS = {
    "top": ("top", "topo"),
    "jungle": ("jungle", "jg", "selva", "jungler"),
    "mid": ("mid", "meio"),
    "adc": ("adc", "bot", "atirador"),
    "support": ("sup", "suporte", "support"),
}
CONTRA_WORD = re.compile(r"\bcontra\b")
BAN_WORDS = re.compile(r"\bban(e|ir|o|imento|ar)?\b")
META_WORDS = re.compile(r"\b(bom|boa|bons|forte|fortes|meta|tier|roubad[oa]s?|op)\b")
TEAM_WORDS = re.compile(r"\b(meu time|nosso time|minha equipe|complementar|time tem|time nao tem)\b")
NEED_WORDS = {
    "carry": re.compile(r"\bcarry\b"),
    "tank": re.compile(r"\b(tank|tanque|frontline)\b"),
    "ap": re.compile(r"\b(ap|dano magico)\b"),
    "ad": re.compile(r"\b(ad|dano fisico)\b"),
}
FULL_DAMAGE = re.compile(r"\b(?:full|so|todo|muito)\s+(ad|ap)\b")
ARTICLES = {"o", "a", "os", "as", "um", "uma"}
MAX_NAME_WORDS = 3  # nomes mais longos: "Nunu & Willump", "Aurelion Sol"...


@dataclass
class Ally:
    champion: str  # nome como veio (LLM: oficial; local: trecho falado)
    position: str | None = None


@dataclass
class Command:
    action: str
    enemy_champion: str | None = None  # nome como veio (LLM: oficial; local: trecho falado)
    my_champion: str | None = None
    position: str | None = None
    allies: list[Ally] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    reply: str | None = None
    # Interpretador local: procurar os campeoes na frase inteira (sem chute).
    find_in_whole_text: bool = False


def route(command_text: str, champion_names: list[str]) -> Command:
    # Sem a lista, o LLM chuta: "ione" virava "Ionia" (a regiao) em vez de
    # Yone. Um enum no schema seria mais rigido, mas o Gemini recusa ~170 valores.
    system = f"{SYSTEM_PROMPT}\nCampeoes existentes: {', '.join(champion_names)}"
    try:
        result = llm.generate_json(f'Transcricao: "{command_text}"', SCHEMA, system)
        return Command(
            action=result.get("action") if result.get("action") in ACTIONS else ACTION_UNKNOWN,
            enemy_champion=result.get("enemy_champion"),
            my_champion=result.get("my_champion"),
            position=result.get("position") if result.get("position") in POSITIONS else None,
            allies=[Ally(a["champion"], a.get("position") if a.get("position") in POSITIONS else None)
                    for a in result.get("allies") or [] if a.get("champion")],
            needs=[n for n in result.get("needs") or [] if n in NEEDS],
            reply=result.get("reply"),
        )
    except llm.LLMError as exc:
        print(f"[Enzo] {exc}; usando interpretador local.")
        return route_locally(command_text)


def route_locally(command_text: str) -> Command:
    """Interpretador por palavras-chave. Pra "ban" e "pick" os campeoes ficam
    pra quem chama achar na frase (find_in_whole_text)."""
    text = normalize(command_text)
    position = detect_position(text)
    if TEAM_WORDS.search(text):
        needs = [need for need, pattern in NEED_WORDS.items() if pattern.search(text)]
        # "time ta full AD" = falta o outro tipo de dano.
        excess = FULL_DAMAGE.search(text)
        if excess:
            needs = [n for n in needs if n not in ("ad", "ap")] + ["ap" if excess.group(1) == "ad" else "ad"]
        return Command(ACTION_PICK, position=position, needs=needs, find_in_whole_text=True)
    if BAN_WORDS.search(text):
        return Command(ACTION_BAN, position=position, find_in_whole_text=True)
    if CONTRA_WORD.search(text):
        # So' as primeiras palavras depois de "contra" podem ser o campeao; o resto
        # da frase ("...que eu vi") poderia bater com nomes curtos como Vi.
        after = re.findall(r"[\w']+", CONTRA_WORD.split(text, 1)[-1])
        while after and after[0] in ARTICLES:
            after.pop(0)
        return Command(ACTION_COUNTER, enemy_champion=" ".join(after[:MAX_NAME_WORDS]), position=position)
    if META_WORDS.search(text) and position:
        return Command(ACTION_META, position=position)
    return Command(ACTION_UNKNOWN)


def detect_position(text: str) -> str | None:
    words = set(re.findall(r"\w+", text.lower()))
    for position, aliases in POSITION_WORDS.items():
        if words.intersection(aliases):
            return position
    return None
