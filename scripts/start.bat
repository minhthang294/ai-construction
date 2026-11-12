@echo off
set ROOT=%~dp0..
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Create .venv and install backend\requirements.txt first
  exit /b 1
)
if not exist "%ROOT%\frontend\node_modules" (
  echo Run npm install in frontend first
  exit /b 1
)
cd /d "%ROOT%\backend"
set SITE_REPORT_STORAGE=%ROOT%\data\storage\site
set ENGINEERING_AI_STORAGE=%ROOT%\data\storage\engineering-ai
set ACCEPTANCE_STORAGE=%ROOT%\data\storage\acceptance
set ACCEPTANCE_TEMPLATE=%ROOT%\data\templates\acceptance-original.xlsx
if "%ENGINEERING_AI_MAX_PDF_BYTES%"=="" set ENGINEERING_AI_MAX_PDF_BYTES=80000000
if "%ENGINEERING_AI_PROVIDER%"=="" set ENGINEERING_AI_PROVIDER=opencode_deepseek
if "%ENGINEERING_AI_OPENCODE_MODEL%"=="" set ENGINEERING_AI_OPENCODE_MODEL=opencode-go/deepseek-v4.1-flash
if "%ENGINEERING_AI_TIMEOUT%"=="" set ENGINEERING_AI_TIMEOUT=180
if "%CONSTRUCTION_API_PORT%"=="" set CONSTRUCTION_API_PORT=8765
"%ROOT%\.venv\Scripts\alembic.exe" upgrade head
if errorlevel 1 exit /b 1
set PYTHONPATH=%ROOT%\backend
start "Construction API" /D "%ROOT%\backend" "%ROOT%\.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port %CONSTRUCTION_API_PORT%
cd /d "%ROOT%\frontend"
npm run dev
