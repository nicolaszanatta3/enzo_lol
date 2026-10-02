# Enzo — assistente de draft de League of Legends

Escolha o campeão e a rota e veja:

1. **Counters**: quem ganha de você e de quem você ganha (média OP.GG + Lolalytics);
2. **Quem banir**: os counters que mais aparecem na rota;
3. **Build**: itens iniciais, botas, core, situacionais, feitiços e ordem de habilidades;
4. **Runas**: a página mais jogada, com a árvore completa.

Dados: [MCP do OP.GG](https://github.com/opgginc/opgg-mcp), API JSON do Lolalytics e Data Dragon da Riot (nomes e imagens em pt-BR).

## Requisitos

- Python 3.11+
- Node.js 20+ (só pra compilar o site)

## Instalação

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # preencha as chaves e o seu Riot ID
cd web; npm install; npm run build; cd ..
```

## Rodar o site

```powershell
venv\Scripts\python.exe -m src.web.server
```

Abre em http://127.0.0.1:8000. No Windows, `iniciar_site.bat` faz tudo isso (e compila o site na primeira vez).

Pra mexer no visual com recarga automática: deixe o servidor acima rodando e use `npm run dev` dentro de `web/`.

## Assistente de voz (opcional)

O fluxo antigo, por voz ("Enzo, tô contra o Malphite no top"), continua em `src/voice`:

```powershell
venv\Scripts\python.exe -m src.voice.voice_assistant
```

Ele precisa do modelo de voz do Piper, que não vai no repositório (61 MB). Baixe o `pt_BR-faber-medium.onnx` e o `.onnx.json` dele de
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR/faber/medium) para `assets/tts/`.
