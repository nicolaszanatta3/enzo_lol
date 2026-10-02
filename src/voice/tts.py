"""Texto -> voz com o Piper (voz local pt-BR, na CPU, sem internet).

Sintetiza frase por frase e toca cada uma assim que fica pronta, entao a fala
comeca em ~0,2s. Nao usa a GPU, que fica pro Whisper e pro jogo.
"""

from functools import lru_cache

import sounddevice as sd
from piper import PiperVoice, SynthesisConfig

from src.core import config


@lru_cache(maxsize=1)
def _voice() -> PiperVoice:
    return PiperVoice.load(str(config.TTS_VOICE_PATH))


def warm_up() -> None:
    """Carrega a voz (~3s) antes da primeira resposta."""
    _voice()


def speak(text: str) -> None:
    voice = _voice()
    syn_config = SynthesisConfig(length_scale=1 / config.TTS_SPEED)
    # Sair do "with" espera o audio pendente terminar de tocar.
    with sd.OutputStream(samplerate=voice.config.sample_rate, channels=1, dtype="float32") as out:
        for chunk in voice.synthesize(text, syn_config=syn_config):  # um pedaco por frase
            out.write(chunk.audio_float_array.reshape(-1, 1))
