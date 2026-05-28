@echo off
setlocal

title Ultimate Media Suite - Build Script
echo ------------------------------------------------------------
echo Ultimate Media Suite - Packaging Project
echo ------------------------------------------------------------

echo 1. Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo 2. Installing requirements...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo 3. Checking application icon...
if exist logo.ico (
    echo Using logo.ico
) else (
    echo logo.ico not found. PyInstaller will use the default icon.
)

echo 4. Starting PyInstaller...
.venv\Scripts\python.exe -m PyInstaller --noconfirm "Ultimate Media Suite.spec"
if errorlevel 1 goto :error

echo ------------------------------------------------------------
echo BUILD COMPLETE: Check the dist folder.
echo ------------------------------------------------------------
pause
exit /b 0

:error
echo ------------------------------------------------------------
echo BUILD FAILED. Check the output above.
echo ------------------------------------------------------------
pause
exit /b 1
