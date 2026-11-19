@echo off
REM Gera dist\NEXUS_BIOMECHANICS\NEXUS_BIOMECHANICS.exe (pasta portátil). Requer venv ativo com requirements.txt.
pip install pyinstaller
pyinstaller nexus.spec --noconfirm
echo.
echo Executavel: dist\NEXUS_BIOMECHANICS\NEXUS_BIOMECHANICS.exe
