@echo off
setlocal
set "PYTHONUNBUFFERED=1"
cd /d "%~dp0"
set "CLEANUP_MODE=clean"
if /I "%~1"=="--preview" set "CLEANUP_MODE=preview"
if not "%~1"=="" if /I not "%~1"=="--preview" (
  echo Usage: "Clean Project.cmd" [--preview]
  exit /b 2
)
echo Cold fixture cleanup: %CLEANUP_MODE%
echo Close test runners first. Owner files, active batches and master builds are protected.
echo A verified lossless archive is required before any selected original is removed.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0scripts\project_cleanup.py" %CLEANUP_MODE%
) else (
  python "%~dp0scripts\project_cleanup.py" %CLEANUP_MODE%
)
set "CLEANUP_RESULT=%ERRORLEVEL%"
echo.
if "%CLEANUP_RESULT%"=="3" (
  echo Cleanup pending: locked files remain. Keep the verified archive and resume the same plan after closing their consumer.
) else if not "%CLEANUP_RESULT%"=="0" (
  echo Cleanup stopped. Originals without verified archives are retained.
)
echo See docs\PROJECT-CLEANUP.md for verification and restore commands.
pause
exit /b %CLEANUP_RESULT%
