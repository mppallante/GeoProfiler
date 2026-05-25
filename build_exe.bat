@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py"
)

if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

echo ========================================
echo GeoProfiler - Windows EXE Builder
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual em .venv...
    if "%PYTHON_CMD%"=="" (
        echo ERRO: Python nao encontrado.
        echo Instale o Python 3 e marque a opcao Add Python to PATH.
        pause
        exit /b 1
    )
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERRO: Nao foi possivel criar o ambiente virtual.
        echo Instale o Python e garanta que ele esteja disponivel no PATH.
        pause
        exit /b 1
    )
)

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERRO: Falha ao atualizar pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo Gerando GeoProfiler.exe...
".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --noconsole ^
    --name GeoProfiler ^
    --add-data "app.py;." ^
    --add-data "requirements.txt;." ^
    --add-data "src;src" ^
    --add-data "data;data" ^
    --add-data "assets;assets" ^
    --add-data ".streamlit;.streamlit" ^
    --collect-all streamlit ^
    --collect-all streamlit_folium ^
    --collect-all folium ^
    --collect-all branca ^
    --collect-all plotly ^
    --collect-all geopandas ^
    launcher.py

if errorlevel 1 (
    echo.
    echo ERRO: Build falhou.
    pause
    exit /b 1
)

echo.
echo Build concluido com sucesso.
echo Executavel gerado em: dist\GeoProfiler.exe
echo.
pause
