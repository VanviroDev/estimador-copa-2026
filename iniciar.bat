@echo off
title Estimador de Probabilidades - Copa do Mundo 2026
color 0A

echo ============================================================
echo   Estimador de Probabilidades - Copa do Mundo 2026
echo ============================================================
echo.
echo Verificando se o Python esta instalado...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERRO] Python nao foi encontrado no seu computador.
    echo Instale o Python em https://www.python.org/downloads/
    echo e marque a opcao "Add python.exe to PATH" durante a instalacao.
    echo.
    pause
    exit /b
)

echo Python encontrado. Verificando dependencias...
python -m pip install --quiet --disable-pip-version-check requests

if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel instalar as dependencias.
    echo Verifique sua conexao com a internet e tente novamente.
    echo.
    pause
    exit /b
)

echo Tudo pronto! Abrindo o programa...
echo.
python "%~dp0estimador_copa_gui.py"

if errorlevel 1 (
    echo.
    echo [ERRO] O programa fechou com um erro. Veja a mensagem acima.
    pause
)
