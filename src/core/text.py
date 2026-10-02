"""Normalizacao de texto transcrito, compartilhada entre voz e LoL."""

import unicodedata


def normalize(text: str) -> str:
    """Minusculas e sem acentos: "Tô contra" -> "to contra"."""
    text = text.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
