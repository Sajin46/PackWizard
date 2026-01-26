@echo off
chcp 65001 >nul
title Быстрая сборка PackWizard

echo Быстрая сборка PackWizard...
echo.

REM Установка зависимостей
echo Устанавливаю зависимости...
pip install -r requirements.txt

REM Установка PyInstaller если нет
pip show pyinstaller >nul 2>&1 || pip install pyinstaller

REM Очистка
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Сборка
pyinstaller --onefile --windowed --icon="icon.ico" --name PackWizard --clean main.py

if errorlevel 1 (
    echo Ошибка сборки!
    pause
    exit /b 1
)

echo.
echo ✅ Сборка завершена!
echo 📍 Файл: dist\PackWizard.exe
pause