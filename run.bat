@echo off
setlocal enabledelayedexpansion

set REPO=https://github.com/EvilPingu-dev/mapGen.git
:: jesli .bat jest wewnatrz sklonowanego repo, uzyj tego katalogu bezposrednio
if exist "%~dp0.git" (
    set APP_DIR=%~dp0
) else (
    set APP_DIR=%~dp0mapGen
)

echo ============================================================
echo  mapGen - Tribal Wars Map Tool
echo ============================================================
echo.

:: ---------- sprawdz uv ----------
where uv >nul 2>&1
if errorlevel 1 (
    echo [*] uv nie znaleziony. Instaluje...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [!] Instalacja uv nie powiodla sie. Zainstaluj recznie: https://docs.astral.sh/uv/
        pause
        exit /b 1
    )
    :: odswierz PATH po instalacji
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
)

:: ---------- sprawdz git ----------
where git >nul 2>&1
if errorlevel 1 (
    echo [!] git nie znaleziony.
    echo     Zainstaluj Git for Windows: https://git-scm.com/download/win
    pause
    exit /b 1
)

:: ---------- klonuj lub aktualizuj repo ----------
if exist "%APP_DIR%\.git" (
    cd /d "%APP_DIR%"
    echo [*] Aktualizuje repo...
    git pull --ff-only
    if errorlevel 1 (
        echo [!] git pull nie powiodl sie. Sprawdz polaczenie lub lokalne zmiany.
        pause
        exit /b 1
    )
    echo [+] Repo zaktualizowane.
) else (
    echo [*] Klonuje repo do %APP_DIR%...
    git clone "%REPO%" "%APP_DIR%"
    if errorlevel 1 (
        echo [!] Klonowanie nie powiodlo sie.
        pause
        exit /b 1
    )
    cd /d "%APP_DIR%"
    echo [+] Repo sklonowane.
)

:: ---------- zainstaluj / zaktualizuj zaleznosci ----------
echo [*] Synchronizuje srodowisko (uv sync)...
uv sync --quiet
if errorlevel 1 (
    echo [!] uv sync nie powiodl sie.
    pause
    exit /b 1
)
echo [+] Srodowisko gotowe.

:: ---------- uruchom web GUI ----------
echo.
echo [*] Uruchamiam mapgen-web na http://127.0.0.1:5000/
echo     Zamknij to okno lub nacisnij Ctrl+C aby zatrzymac.
echo.

:: otworz przegladarke po krotkim opoznieniu (daj czas serwerowi na start)
powershell -Command "Start-Sleep 2; Start-Process 'http://127.0.0.1:5000/'" >nul 2>&1 &

uv run mapgen-web

pause
