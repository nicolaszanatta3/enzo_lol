"""Ponto unico de acesso aos LLMs: tenta o Groq (~0,8s por pedido) e, se ele
falhar (cota, fora do ar, resposta invalida), o Gemini (~2,5s)."""

from src.ai import gemini, groq

# (nome, modulo, erro que o modulo levanta quando nao consegue responder)
PROVIDERS = (
    ("Groq", groq, groq.GroqError),
    ("Gemini", gemini, gemini.GeminiError),
)


class LLMError(RuntimeError):
    pass


def _first_that_answers(function: str, *args):
    failures = []
    for name, module, error in PROVIDERS:
        try:
            return getattr(module, function)(*args)
        except (error, ValueError) as exc:  # ValueError: JSON invalido
            print(f"[Enzo] {name} falhou: {str(exc)[:150]}")
            failures.append(name)
    raise LLMError("nenhum LLM respondeu: " + ", ".join(failures))


def generate_json(prompt: str, schema: dict, system: str) -> dict:
    return _first_that_answers("generate_json", prompt, schema, system)


def generate_text(prompt: str, system: str) -> str:
    return _first_that_answers("generate_text", prompt, system)
