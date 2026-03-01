@echo off
if exist "venv" (
    call venv\Scripts\activate
) else (
    echo "Warning: venv not found. Ensure PyInstaller is installed globally."
)

pyinstaller k_backups.spec --clean --noconfirm
pause
