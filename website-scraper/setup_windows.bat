@echo off
setlocal
cd /d "%~dp0"
echo ==================================================
echo ScrapeFlow Universal Scraper - Windows Setup
echo Do not close this window while packages install.
echo ==================================================
echo [1/5] Creating virtual environment...
if not exist venv py -m venv venv
if errorlevel 1 goto :error
call venv\Scripts\activate.bat

echo [2/5] Updating pip, setuptools and wheel...
python -m pip install --upgrade pip setuptools wheel --prefer-binary
if errorlevel 1 goto :error

echo [3/5] Installing lightweight Python packages...
python -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 goto :error

echo [4/5] Installing Chromium for Playwright...
python -m playwright install chromium
if errorlevel 1 goto :error

if not exist .env copy .env.example .env >nul
echo [5/5] Setup complete.
echo Run run_windows.bat to start ScrapeFlow.
pause
exit /b 0

:error
echo.
echo Setup failed. Do not press Ctrl+C during installation.
echo You can safely run setup_windows.bat again.
pause
exit /b 1
