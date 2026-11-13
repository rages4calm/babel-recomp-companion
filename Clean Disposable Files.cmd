@echo off
setlocal
title Illusion of Gaia - disposable files cleanup
echo Processing reviewed prank/old EXEs, old compiler objects and approved historical raw output.
echo Pass -Preview to inspect these allowlists without deleting files.
echo Current 019 work, complete 018 proof, retained v18, owner files, music and SDKs are protected.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\cleanup_disposable.ps1" %*
set "cleanup_exit=%errorlevel%"
if not "%cleanup_exit%"=="0" goto cleanup_done
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\cleanup_obsolete_objects.ps1" %*
set "cleanup_exit=%errorlevel%"
if not "%cleanup_exit%"=="0" goto cleanup_done
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\retire_old_raw.ps1" %*
set "cleanup_exit=%errorlevel%"
:cleanup_done
echo.
if not "%cleanup_exit%"=="0" echo Some files were retained. Read the receipt, close their consumers and rerun.
if "%~1"=="" pause
exit /b %cleanup_exit%
