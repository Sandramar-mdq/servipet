@echo off
cd /d %~dp0

echo [1/4] Aplicando migraciones (alembic upgrade head)...
python -m alembic upgrade head
if errorlevel 1 goto :error

echo [2/4] Poblando datos semilla (scripts/seed_demo.py)...
python scripts/seed_demo.py
if errorlevel 1 goto :error

echo [3/4] Programando apertura del navegador...
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000/"

echo [4/4] Iniciando servidor Uvicorn (Ctrl+C para detener)...
python -m uvicorn app.main:app --reload
goto :eof

:error
echo.
echo ERROR: fallo la preparacion. Revise el mensaje anterior.
pause