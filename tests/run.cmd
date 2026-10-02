@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d "%~dp0.."
cl /nologo /std:c++17 /utf-8 /EHsc /MT tests\save_sync_test.cpp /Fo:build\save_sync_test.obj user32.lib gdi32.lib advapi32.lib /link /OUT:build\save_sync_test.exe
if errorlevel 1 exit /b 1
build\save_sync_test.exe
