"""Acesso ao Gemini (chave em GEMINI_API_KEY no .env).

O plano gratuito tem cota POR MODELO (ex: 20 pedidos/dia no 2.5-flash-lite).
Pra render mais, `config.GEMINI_MODELS` lista varios modelos: quando um
estoura a cota (429) ou esta sobrecarregado (503), passa pro proximo e deixa
o que falhou "de castigo" ate a cota voltar.
"""

import json
import re
import time
from functools import lru_cache

from google import genai
from google.genai import types

from src.core import config

# Quanto tempo pular um modelo depois de uma falha, quando a API nao diz.
DAILY_QUOTA_COOLDOWN = 60 * 60
OVERLOAD_COOLDOWN = 60

_unavailable_until: dict[str, float] = {}


class GeminiError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    if not config.GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY nao configurada no .env")
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _cooldown_for(error: str) -> float | None:
    """Segundos pra pular o modelo, ou None se o erro nao e' de cota/sobrecarga."""
    if "RESOURCE_EXHAUSTED" in error or "429" in error:
        if "PerDay" in error:
            return DAILY_QUOTA_COOLDOWN
        retry = re.search(r"retry in ([\d.]+)s", error)
        return float(retry.group(1)) if retry else OVERLOAD_COOLDOWN
    if "UNAVAILABLE" in error or "503" in error:
        return OVERLOAD_COOLDOWN
    return None


def _generate(prompt: str, **generation_options) -> str:
    failures = []
    for model, thinking_level in config.GEMINI_MODELS:
        if _unavailable_until.get(model, 0) > time.time():
            continue
        options = dict(generation_options)
        if thinking_level:
            # Modelos 3.x "pensam" por padrao; minimal deixa a resposta ~0.5s.
            options["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)
        try:
            response = _client().models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig(**options)
            )
        except Exception as exc:
            error = str(exc)
            cooldown = _cooldown_for(error)
            if cooldown is None:
                raise GeminiError(f"{model}: {error[:200]}") from exc
            _unavailable_until[model] = time.time() + cooldown
            failures.append(f"{model} ({error.split('.')[0]})")
            continue
        if response.text:
            return response.text.strip()
        failures.append(f"{model} (resposta vazia)")
    raise GeminiError("sem modelo disponivel: " + (", ".join(failures) or "todos em espera por cota"))


def generate_json(prompt: str, schema: dict, system: str) -> dict:
    """Gera uma resposta estruturada seguindo `schema` (JSON Schema do Gemini)."""
    text = _generate(
        prompt,
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0,
    )
    return json.loads(text)


def generate_text(prompt: str, system: str) -> str:
    return _generate(prompt, system_instruction=system, temperature=0.7)
