"""Assistente de voz "Enzo": escuta o microfone continuamente e responde falando
(ver src/core/enzo.py).

Rodar a partir da raiz do projeto:
    python -m src.voice.voice_assistant

Fluxo:
    microfone -> Silero VAD -> trecho de fala
    -> detector (Whisper pequeno, ~0,2s): o nome "Enzo" esta' nas primeiras palavras?
       Checado ja' DURANTE a fala, entao o bipe sai antes de voce terminar.
    -> so' se foi chamado: Whisper grande transcreve o comando -> Enzo responde

Formas de chamar:
    "Enzo, to contra o Malphite"
    "Enzo" ... (bipe) ... "to contra o Malphite"   (ate' config.COMMAND_TIMEOUT)
"""

import difflib
import re
import sys
import threading
import time
import winsound

from src.core import config
from src.core.enzo import Enzo
from src.core.text import normalize
from src.voice import stt, tts
from src.voice.vad_listener import listen_for_utterances

WAKE_WORD_FUZZY_THRESHOLD = 0.75  # tolera "Enso", "Henzo"...


def split_wake_word(text: str) -> str | None:
    """Comando depois do nome ("" se veio so' o nome) ou None se o Enzo nao foi chamado."""
    words = text.split()
    for i, word in enumerate(words[: config.WAKE_WORD_MAX_WORDS_BEFORE + 1]):
        letters = re.sub(r"[^a-z]", "", normalize(word))
        if letters and difflib.SequenceMatcher(None, letters, config.WAKE_WORD).ratio() >= WAKE_WORD_FUZZY_THRESHOLD:
            return " ".join(words[i + 1:]).strip(" ,.!?;:-")
    return None


def beep() -> None:
    winsound.Beep(880, 120)


def run():
    sys.stdout.reconfigure(encoding="utf-8")  # dicas do OP.GG vem com aspas tipograficas

    enzo = Enzo()
    # Busca pool e tabelas de confronto enquanto os modelos de voz carregam.
    warm_up = enzo.warm_up_in_background()

    print("Carregando modelos de voz (Whisper e Piper)...")
    detector, command_model = stt.load_models()
    tts.warm_up()

    mic_muted = threading.Event()

    def say(text: str) -> None:
        # Surda o microfone enquanto fala, senao o Enzo pode se ouvir e entrar em loop.
        print(f"Enzo: {text}")
        mic_muted.set()
        try:
            tts.speak(text)
        finally:
            mic_muted.clear()

    def answer(command_text: str, heard_at: float) -> None:
        print(f'Voce: "{command_text}"')
        try:
            reply = enzo.handle(command_text)
        except Exception as exc:  # rede/MCP/Riot fora do ar nao pode derrubar a escuta
            print(f"Erro ao responder: {exc}")
            say("Deu ruim aqui pra buscar os dados. Tenta de novo daqui a pouco.")
            return
        if reply.console:
            print(reply.console)
        print(f"(resposta em {time.perf_counter() - heard_at:.1f}s)")
        say(reply.speech)
        if reply.followup:
            tip = reply.followup.result()
            if tip:
                say(tip)

    try:
        warm_up.result()
        print("Dados do LoL carregados (pool e confrontos).")
    except Exception as exc:  # sem internet etc.: tenta de novo na primeira pergunta
        print(f"Nao consegui pre-carregar os dados do LoL: {exc}")

    print(f'Assistente "{config.ASSISTANT_NAME}" ativo. Diga: "{config.ASSISTANT_NAME}, to contra <campeao>".')

    command_deadline = 0.0  # prazo pro comando depois de "Enzo" sozinho
    called = False  # o nome ja' foi ouvido numa parcial do trecho atual

    for kind, audio in listen_for_utterances(mute_event=mic_muted):
        waiting_command = time.monotonic() < command_deadline

        if kind == "partial":
            if not (waiting_command or called):
                if split_wake_word(stt.transcribe_fast(detector, audio)) is not None:
                    called = True
                    beep()
            continue

        # kind == "end": trecho completo
        heard_at = time.perf_counter()
        was_called, called = called, False
        if waiting_command:
            command_deadline = 0.0
            command = stt.transcribe(command_model, audio)
        else:
            quick = split_wake_word(stt.transcribe_fast(detector, audio))
            if not was_called:
                if quick is None:
                    continue  # ninguem chamou o Enzo
                beep()
            if quick == "":  # so' o nome: o comando vem no proximo trecho
                command_deadline = time.monotonic() + config.COMMAND_TIMEOUT
                continue
            text = stt.transcribe(command_model, audio)
            command = split_wake_word(text)
            if command is None:  # o detector ouviu o nome e o modelo grande nao: vale o detector
                command = text
        if command:
            answer(command, heard_at)


if __name__ == "__main__":
    run()
