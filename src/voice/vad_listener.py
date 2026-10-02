"""Captura continua do microfone, segmentando a fala com o Silero VAD (o mesmo
modelo que o faster-whisper traz embutido), quadro a quadro.

Gera eventos (tipo, audio float32 16kHz mono):
  ("partial", ...) a cada ~1s enquanto a fala continua, pra achar o nome cedo;
  ("end", ...)     o trecho completo, depois de SILENCE_SECONDS de silencio.
"""

import collections
import queue
import threading

import numpy as np
import sounddevice as sd
from faster_whisper.vad import get_vad_model

from src.core import config

FRAME_SAMPLES = 512  # 32 ms: tamanho de quadro que o Silero espera
CONTEXT_SAMPLES = 64  # fim do quadro anterior, que o Silero usa como contexto
FRAME_SECONDS = FRAME_SAMPLES / config.SAMPLE_RATE
SPEECH_THRESHOLD = 0.5
SILENCE_THRESHOLD = 0.35
SILENCE_SECONDS = 0.6
PREBUFFER_SECONDS = 0.3  # audio mantido antes do inicio da fala, pra nao cortar a 1a silaba
MIN_SPEECH_SECONDS = 0.25  # menos que isso e' estalo/tosse
MAX_SPEECH_SECONDS = 15.0
PARTIAL_EVERY_SECONDS = 1.0
PARTIAL_UNTIL_SECONDS = 2.5  # o nome vem nas primeiras palavras; depois disso nao adianta


class _SileroStream:
    def __init__(self):
        self._session = get_vad_model().session
        self._context = np.zeros(CONTEXT_SAMPLES, dtype=np.float32)
        self._state = np.zeros((1, 1, 128), dtype=np.float32)

    def speech_prob(self, frame: np.ndarray) -> float:
        audio = np.concatenate([self._context, frame])[None, :]
        output, _, _ = self._session.run(None, {"input": audio, "h": self._state, "c": self._state})
        self._context = frame[-CONTEXT_SAMPLES:]
        return float(output.ravel()[0])


def listen_for_utterances(mute_event: threading.Event | None = None):
    """mute_event: quando setado, os quadros sao descartados. Usado pra "surdear"
    o microfone enquanto o TTS toca, senao o Enzo se ouve e entra em loop.
    """
    vad = _SileroStream()
    frame_queue: "queue.Queue[np.ndarray]" = queue.Queue()

    def callback(indata, frames, time_info, status):
        if mute_event is not None and mute_event.is_set():
            return
        frame_queue.put(indata[:, 0].copy())

    prebuffer = collections.deque(maxlen=int(PREBUFFER_SECONDS / FRAME_SECONDS))
    voiced_frames: list[np.ndarray] = []
    silence_frames = 0
    next_partial = 0.0

    with sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=FRAME_SAMPLES,
        callback=callback,
    ):
        while True:
            frame = frame_queue.get()
            prob = vad.speech_prob(frame)

            if not voiced_frames:
                if prob >= SPEECH_THRESHOLD:
                    voiced_frames = [*prebuffer, frame]
                    silence_frames = 0
                    next_partial = PREBUFFER_SECONDS + PARTIAL_EVERY_SECONDS
                else:
                    prebuffer.append(frame)
                continue

            voiced_frames.append(frame)
            silence_frames = silence_frames + 1 if prob < SILENCE_THRESHOLD else 0
            duration = len(voiced_frames) * FRAME_SECONDS
            silence = silence_frames * FRAME_SECONDS

            if silence >= SILENCE_SECONDS or duration >= MAX_SPEECH_SECONDS:
                if duration - silence >= MIN_SPEECH_SECONDS:
                    yield "end", np.concatenate(voiced_frames)
                voiced_frames = []
                prebuffer.clear()
            elif duration >= next_partial and next_partial <= PREBUFFER_SECONDS + PARTIAL_UNTIL_SECONDS:
                next_partial += PARTIAL_EVERY_SECONDS
                yield "partial", np.concatenate(voiced_frames)
