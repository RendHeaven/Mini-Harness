@echo off
setlocal

if not defined HARNESS_PYTHON set "HARNESS_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%HARNESS_PYTHON%" exit /b 127

"%HARNESS_PYTHON%" -B -X utf8 "%~dp0usage_hook.py"
exit /b %ERRORLEVEL%
