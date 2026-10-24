@echo off
echo Starting Cashflow Forecasting Application...

pushd "%~dp0backend"
start "Cashflow Backend (FastAPI)" cmd /k "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
popd

pushd "%~dp0frontend"
start "Cashflow Frontend (Vite)" cmd /k "npm run dev"
popd

echo Backend running on http://127.0.0.1:8000
echo Frontend running on http://localhost:5173/
ping 127.0.0.1 -n 4 >nul
start http://localhost:5173/
