@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

where uv >nul 2>nul
if errorlevel 1 (
  echo [InstaTrip] 'uv' introuvable. Installe-le : https://docs.astral.sh/uv/
  echo Puis relance run.bat
  pause
  exit /b 1
)

echo [InstaTrip] Installation des dependances (uv sync)...
call uv sync
if errorlevel 1 ( echo [InstaTrip] echec uv sync & pause & exit /b 1 )

echo [InstaTrip] Installation du navigateur Playwright...
call uv run playwright install chromium

echo [InstaTrip] Lancement de l'assistant Claude...
claude "Tu es l'assistant InstaTrip. InstaTrip transforme une collection Instagram 'Enregistrements' en fichier Excel + notes Obsidian. Invoque la skill instatrip-collection pour guider l'utilisateur (creation d'une nouvelle collection en demandant le lien Instagram, ou reprise d'une collection existante pour recuperer les nouveaux posts). Rappelle que l'analyse passe par l'abonnement Claude Code, sans cle API. Si la session Instagram est perimee, indique de lancer 'uv run instatrip auth'."

endlocal
