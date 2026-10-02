"""Fala -> texto com faster-whisper, na GPU quando disponivel.

Dois modelos (ver config.WHISPER_*_MODEL): o detector, rapido, so' procura o
nome do Enzo em cada trecho de fala; o de comando, preciso, so' roda depois
que o Enzo foi chamado.

As DLLs do CUDA (cuBLAS/cuDNN) vem dos pacotes pip nvidia-cublas-cu12 e
nvidia-cudnn-cu12, instalados dentro da venv. O Windows nao acha essas DLLs
sozinho, entao as pastas `bin` sao registradas antes de carregar o modelo.
Na GTX 1050 Ti (Pascal) so' int8/float32 rodam bem; float16 nao.
"""

import glob
import os
import sys

import numpy as np

from src.core import config


def _register_cuda_dlls() -> None:
    pattern = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "*", "bin")
    for dll_dir in glob.glob(pattern):
        os.add_dll_directory(dll_dir)
        # O CTranslate2 carrega algumas DLLs pelo PATH, nao pelo add_dll_directory.
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")


def _load(size: str):
    from faster_whisper import WhisperModel

    model = None
    if config.WHISPER_DEVICE in ("auto", "cuda"):
        try:
            model = WhisperModel(size, device="cuda", compute_type="int8")
            print(f"Whisper {size} rodando na GPU.")
        except Exception as exc:  # sem placa NVIDIA, driver velho, DLL faltando...
            if config.WHISPER_DEVICE == "cuda":
                raise
            print(f"GPU indisponivel pro Whisper {size}, usando CPU: {exc}")
    if model is None:
        model = WhisperModel(size, device="cpu", compute_type="int8")
    # A primeira transcricao inicializa o CUDA (~1s); melhor aqui que no 1o comando.
    # (os segmentos sao um gerador: list() forca a transcricao a acontecer)
    silence = np.zeros(config.SAMPLE_RATE, dtype=np.float32)
    list(model.transcribe(silence, language=config.WHISPER_LANGUAGE)[0])
    return model


def load_models():
    """Devolve (detector, modelo de comando)."""
    _register_cuda_dlls()
    return _load(config.WHISPER_DETECTOR_MODEL), _load(config.WHISPER_COMMAND_MODEL)


def transcribe_fast(model, audio: np.ndarray) -> str:
    """Transcricao rapida e grosseira, suficiente pra achar o nome do Enzo."""
    segments, _ = model.transcribe(
        audio,
        language=config.WHISPER_LANGUAGE,
        beam_size=1,
        without_timestamps=True,
        hotwords=config.ASSISTANT_NAME,
    )
    return " ".join(seg.text for seg in segments).strip()


def transcribe(model, audio: np.ndarray) -> str:
    segments, _ = model.transcribe(
        audio,
        language=config.WHISPER_LANGUAGE,
        beam_size=5,
        # Exemplo do tipo de frase esperada: puxa a grafia de "Enzo" e dos
        # nomes de campeao (ex: "Kai'Sa" em vez de "caixa").
        initial_prompt=config.WHISPER_PROMPT,
    )
    return " ".join(seg.text for seg in segments).strip()
