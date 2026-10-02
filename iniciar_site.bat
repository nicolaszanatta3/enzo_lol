@echo off
rem Abre o site do Enzo (counters, bans, build e runas) em http://127.0.0.1:8000
cd /d "%~dp0"
if not exist "web\dist\index.html" (
    echo Compilando o site pela primeira vez...
    pushd web
    call npm install && call npm run build
    popd
)
"venv\Scripts\python.exe" -m src.web.server
pause
