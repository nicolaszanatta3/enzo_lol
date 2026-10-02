"""Configuracao central: nomes, caminhos, limiares e dados do jogador."""

import os
from pathlib import Path

from dotenv import load_dotenv

# src/core/config.py -> sobe 3 niveis (core -> src -> raiz do projeto)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"

load_dotenv(PROJECT_ROOT / ".env")

# --- Geral ---
ASSISTANT_NAME = "Enzo"

# --- Voz ---
SAMPLE_RATE = 16000
WAKE_WORD = "enzo"
# O nome pode vir depois de ate' N palavras ("Ei, Enzo", "Fala, Enzo"); mais longe
# que isso e' conversa que so' cita o Enzo ("Ontem o Enzo me ajudou").
WAKE_WORD_MAX_WORDS_BEFORE = 1
COMMAND_TIMEOUT = 6.0  # segundos pra falar o comando depois de "Enzo" sozinho

WHISPER_LANGUAGE = "pt"
WHISPER_DEVICE = "auto"  # "auto" tenta a GPU (CUDA) e cai pra CPU; ou "cuda"/"cpu"
# Dois modelos: um rapido so' pra achar o nome (roda em todo trecho de fala,
# ~0,2s na GTX 1050 Ti) e um preciso pro comando (~1,5s; o small errava numeros).
WHISPER_DETECTOR_MODEL = "base"
WHISPER_COMMAND_MODEL = "large-v3-turbo"
WHISPER_PROMPT = (
    "Enzo, tô contra o Malphite no top, do que eu jogo? Enzo, tô contra a Akali no mid. "
    "Enzo, tô contra a Kai'Sa. Enzo, tô contra o K'Sante no top. "
    "Enzo, quero jogar de Fizz, o que eu devo banir? Enzo, o que tá bom no top? "
    "Enzo, meu time é Naafiri, Vladimir, Jinx e Lulu, o que eu pego?"
)

# Voz local do Piper (na CPU, sem internet); a GPU fica pro Whisper e pro jogo.
TTS_VOICE_PATH = ASSETS_DIR / "tts" / "pt_BR-faber-medium.onnx"
TTS_SPEED = 1.1  # um pouco mais rapido que o normal, pra resposta nao arrastar

# --- LLMs (entendem o comando e traduzem dicas) ---
# O Groq e' o principal (mais rapido); se todos os modelos dele falharem (cota,
# fora do ar), o Gemini assume (ver src/ai/llm.py).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Tentados em ordem; cada um tem sua propria cota diaria no plano gratuito.
# (modelo, thinking_level): os 3.x "pensam" por padrao e ficam lentos, entao
# vao com "minimal"; o 2.5-flash-lite nao pensa e nao aceita esse parametro.
GEMINI_MODELS = [
    ("gemini-2.5-flash-lite", None),
    ("gemini-3.5-flash-lite", "minimal"),
    ("gemini-flash-lite-latest", "minimal"),
]

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# (modelo, reasoning_effort): os gpt-oss "pensam"; "low" deixa a resposta rapida.
GROQ_MODELS = [
    ("openai/gpt-oss-120b", "low"),
    ("openai/gpt-oss-20b", "low"),
]

# --- League of Legends ---
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
# Seu Riot ID (Nome#TAG), no .env: o pool de campeoes sai do seu perfil.
RIOT_GAME_NAME = os.getenv("RIOT_GAME_NAME", "")
RIOT_TAG_LINE = os.getenv("RIOT_TAG_LINE", "")
RIOT_REGIONAL_ROUTE = "americas"  # API account-v1 (Riot ID -> puuid)
RIOT_PLATFORM = "br1"  # APIs especificas do servidor (maestria etc.)
OPGG_REGION = "BR"
OPGG_MCP_URL = "https://mcp-api.op.gg/mcp"

# Rota usada quando a pergunta nao cita uma (ex: "Enzo, to contra Malphite no mid").
MAIN_POSITION = "top"
# Quantos campeoes entram no pool vindo de cada fonte (mais jogados + maestria).
POOL_SIZE = 10
# Counters falados em voz alta / listados no console (quem voce joga aparece
# no console mesmo fora do top).
COUNTERS_SPOKEN = 5
COUNTERS_CONSOLE = 10
# Elo das estatisticas do Lolalytics (emerald_plus, diamond_plus, all, gold...).
LOLALYTICS_TIER = "emerald_plus"

# --- Fase de escolha: meta, ban e pick (src/lol/draft.py) ---
# Meta ("o que ta bom no top?"): quantos falar / listar; abaixo desse pick
# rate e' escolha de nicho (ex: Qiyana top S+ com 0,3% das partidas).
META_SPOKEN = 5
META_CONSOLE = 15
META_MIN_PICK_RATE = 0.01
BANS_SPOKEN = 3
BANS_CONSOLE = 8
# Pick ("meu time e'..."): candidatos precisam ser jogados na rota (menos os do pool).
PICK_SPOKEN = 3
PICK_CONSOLE = 10
PICK_MIN_PICK_RATE = 0.01
# Bonus na nota por suprir algo que falta no time (sem frontline, so' dano
# fisico...), em pontos de winrate: 2% ~ o peso de uma sinergia muito boa.
COMPOSITION_BONUS = 0.02
