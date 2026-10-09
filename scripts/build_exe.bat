@echo off
rem Builds the Windows download: dist\AlgoTradingLab\ (the app) and dist\AlgoTradingLab-<version>-windows.zip
rem plus a SHA256.txt to publish next to it.
rem
rem   scripts\build_exe.bat [version]            e.g. scripts\build_exe.bat 1.0.0
rem
rem It uses its own virtual environment (.venv-build), so your normal one is untouched. If PyInstaller doesn't
rem support the newest Python yet, point it at an older one first:   set BUILD_PYTHON=py -3.13
cd /d "%~dp0.."
set VERSION=%~1
if "%VERSION%"=="" set VERSION=1.0.0
if "%BUILD_PYTHON%"=="" set BUILD_PYTHON=python

if not exist ".venv-build\Scripts\python.exe" (
  %BUILD_PYTHON% -m venv .venv-build || goto :failed
)
rem The app's own requirements, minus the test tools, plus the packager.
findstr /v /b /i "pytest" requirements.txt > .venv-build\runtime-requirements.txt
".venv-build\Scripts\python.exe" -m pip install --quiet -r .venv-build\runtime-requirements.txt pyinstaller || goto :failed

if exist "dist\AlgoTradingLab" rmdir /s /q "dist\AlgoTradingLab"
".venv-build\Scripts\python.exe" -m PyInstaller scripts\algo_lab.spec --noconfirm --distpath dist --workpath build || goto :failed

set ZIP=dist\AlgoTradingLab-%VERSION%-windows.zip
if exist "%ZIP%" del "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\AlgoTradingLab' -DestinationPath '%ZIP%'; (Get-FileHash '%ZIP%' -Algorithm SHA256).Hash.ToLower() + '  ' + (Split-Path '%ZIP%' -Leaf) | Set-Content -Encoding ascii 'dist\SHA256.txt'" || goto :failed

echo.
echo Built %ZIP%
type dist\SHA256.txt
goto :eof

:failed
echo.
echo The build failed. See the messages above.
exit /b 1
