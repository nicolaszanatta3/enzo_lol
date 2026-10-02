"""Cliente minimo do MCP do OP.GG (https://github.com/opgginc/opgg-mcp).

O servidor fala JSON-RPC via "Streamable HTTP": um POST por chamada, e a
resposta pode vir como JSON puro ou como Server-Sent Events (linhas "data:").

As ferramentas que aceitam `desired_output_fields` devolvem um formato
compacto parecido com construtores Python, por exemplo:

    class Data: champions
    class Champion: champion_id,name

    Root(Data([Champion(1,"Annie"),Champion(2,"Olaf")]))

`_parse_compact` converte isso em dicts/listas comuns. Ferramentas sem esse
parametro (ex: lol_get_lane_matchup_guide) devolvem JSON normal.
"""

import itertools
import json
import re
import threading

import httpx

from src.core import config

PROTOCOL_VERSION = "2025-03-26"


class McpError(RuntimeError):
    pass


class OpggMcpClient:
    def __init__(self, url: str = config.OPGG_MCP_URL, timeout: float = 60):
        self._url = url
        self._http = httpx.Client(timeout=timeout)
        self._session_id: str | None = None
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _post(self, payload: dict) -> httpx.Response:
        return self._http.post(self._url, headers=self._headers(), json=payload)

    def _ensure_session(self) -> None:
        with self._lock:
            if self._session_id:
                return
            response = self._post({
                "jsonrpc": "2.0",
                "id": next(self._ids),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "enzo", "version": "0.1"},
                },
            })
            response.raise_for_status()
            self._session_id = response.headers.get("mcp-session-id")
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call_tool(self, name: str, arguments: dict):
        """Chama uma ferramenta e devolve o resultado ja convertido em dict/list."""
        self._ensure_session()
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        response = self._post(payload)
        if response.status_code == 404 and self._session_id:
            # Sessao expirou no servidor: abre outra e tenta de novo uma vez.
            self._session_id = None
            self._ensure_session()
            response = self._post(payload)
        response.raise_for_status()

        message = _read_jsonrpc(response)
        if "error" in message:
            raise McpError(f"{name}: {message['error'].get('message')}")
        result = message["result"]
        text = "".join(c.get("text", "") for c in result.get("content", []))
        if result.get("isError"):
            raise McpError(f"{name}: {text}")
        return _parse_tool_text(text)


def _read_jsonrpc(response: httpx.Response) -> dict:
    if "text/event-stream" in response.headers.get("content-type", ""):
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:])
        raise McpError("Resposta SSE sem linha 'data:'")
    return response.json()


def _parse_tool_text(text: str):
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        return json.loads(stripped)
    return _parse_compact(stripped)


# --- Parser do formato compacto -------------------------------------------

_CLASS_LINE = re.compile(r"^class (\w+): (.*)$")
_TOKEN = re.compile(
    r'\s*(?:(?P<str>"(?:[^"\\]|\\.)*")|(?P<num>-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)'
    r"|(?P<name>[A-Za-z_]\w*)|(?P<punct>[()\[\],]))"
)


def _parse_compact(text: str):
    classes: dict[str, list[str]] = {}
    body_lines = []
    for line in text.splitlines():
        match = _CLASS_LINE.match(line)
        if match:
            classes[match.group(1)] = [f.strip() for f in match.group(2).split(",")]
        elif line.strip():
            body_lines.append(line)

    tokens = [m for m in _TOKEN.finditer("\n".join(body_lines))]
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def expect(char: str):
        nonlocal pos
        token = peek()
        if token is None or token.group("punct") != char:
            raise McpError(f"Formato inesperado do MCP: esperava '{char}'")
        pos += 1

    def parse_sequence(closing: str) -> list:
        nonlocal pos
        items = []
        if peek() is not None and peek().group("punct") == closing:
            pos += 1
            return items
        while True:
            items.append(parse_value())
            token = peek()
            pos += 1
            if token is None:
                raise McpError("Formato inesperado do MCP: fim antes do fechamento")
            if token.group("punct") == closing:
                return items
            if token.group("punct") != ",":
                raise McpError("Formato inesperado do MCP: separador invalido")

    def parse_value():
        nonlocal pos
        token = peek()
        if token is None:
            raise McpError("Formato inesperado do MCP: valor ausente")
        pos += 1
        if token.group("str") is not None:
            return json.loads(token.group("str"))
        if token.group("num") is not None:
            number = token.group("num")
            return float(number) if any(c in number for c in ".eE") else int(number)
        if token.group("punct") == "[":
            return parse_sequence("]")
        name = token.group("name")
        if name in ("null", "None"):
            return None
        if name in ("true", "True", "false", "False"):
            return name.lower() == "true"
        expect("(")
        args = parse_sequence(")")
        fields = classes.get(name)
        if fields is None or len(fields) != len(args):
            return args
        return dict(zip(fields, args))

    # A raiz tem o nome da ferramenta (ex: "class LolGetSummonerProfile: data"),
    # entao vira {"data": ...} -- mesmo formato das respostas em JSON.
    return parse_value()
