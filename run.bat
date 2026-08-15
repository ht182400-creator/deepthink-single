@echo off
chcp 65001 >nul
cd /d %~dp0

echo ============================================
echo   Stock Main-force Tracker (deepthinkSingle)
echo   open http://localhost:5000
echo ============================================
echo.

echo [1/4] Killing old processes (port 5000 + all app.py)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000 " ^| findstr "LISTENING"') do (
  taskkill /F /PID %%a >nul 2>nul
)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

where python >nul 2>nul
if %errorlevel% neq 0 (
  if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  ) else (
    echo [ERROR] Python not found.
    pause
    exit /b 1
  )
) else (
  set "PY=python"
)

%PY% -c "import flask, requests" 2>nul
if %errorlevel% neq 0 (
  echo Installing flask + requests...
  %PY% -m pip install --quiet flask requests
)

echo [4/4] Starting server...
:: 在独立窗口后台启动服务（保留日志/可关闭），主窗口等待端口就绪后再开浏览器
start "" cmd /c "%PY% app.py"

set /a "_wait=0"
:wait
curl -s -o nul http://localhost:5000/api/sysinfo >nul 2>nul
if %errorlevel%==0 goto :opened
set /a "_wait+=1"
if %_wait% geq 30 (
  echo Server did not start within 30s. Check the server window for errors.
  goto :opened
)
timeout /t 1 /nobreak >nul
goto :wait
:opened
start "" "http://localhost:5000"
echo Server is up - opened http://localhost:5000

pause
