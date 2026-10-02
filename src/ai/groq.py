"""Acesso ao Groq (chave em GROQ_API_KEY no .env), LLM principal do Enzo.

A API e' compativel com a da OpenAI. Como no Gemini, a cota do plano gratuito
e' por modelo: quando um estoura (429) ou esta sobrecarregado (503), passa pro
proximo de `config.GROQ_MODELS`.
"""

import json

import httpx

from src.core import config

URL = "https://api.groq.com/openai/v1/chat/completions"
RETRYABLE_STATUS = (429, 503)


class GroqError(RuntimeError):
    pass


def _generate(system: str, prompt: str, **options) -> str:
    if not config.GROQ_API_KEY:
        raise GroqError("GROQ_API_KEY nao configurada no .env")
    failures = []
    for model, reasoning_effort in config.GROQ_MODELS:
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            **options,
        }
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        try:
            response = httpx.post(
                URL, json=body, headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"}, timeout=20
            )
        except httpx.HTTPError as exc:  # rede: os outros modelos falhariam igual
            raise GroqError(f"{model}: {exc}") from exc
        if response.status_code in RETRYABLE_STATUS:
            failures.append(f"{model} ({response.status_code})")
            continue
        if response.status_code != 200:
            raise GroqError(f"{model}: {response.status_code} {response.text[:200]}")
        text = response.json()["choices"][0]["message"].get("content")
        if text:
            return text.strip()
        failures.append(f"{model} (resposta vazia)")
    raise GroqError("sem modelo disponivel: " + ", ".join(failures))


def generate_json(prompt: str, schema: dict, system: str) -> dict:
    """Resposta em JSON. O modo json_object do Groq garante JSON valido; o
    formato vai descrito no prompt (o schema e' o mesmo usado no Gemini)."""
    system = f"{system}\nResponda so' com um objeto JSON neste formato (JSON Schema):\n{json.dumps(schema)}"
    text = _generate(system, prompt, response_format={"type": "json_object"}, temperature=0)
    return json.loads(text)


def generate_text(prompt: str, system: str) -> str:
    return _generate(system, prompt, temperature=0.7)
