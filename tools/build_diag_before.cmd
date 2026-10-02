@echo off
cd /d "%~dp0.."
call "C:\Program Files\Microsoft Visual Studio\2022\VC\Auxiliary\Build\vcvars64.bat" >nul
pushd build
cl /nologo /std:c++17 /utf-8 /O2 /MT /W4 /EHsc diag_before.cpp toolset.res user32.lib gdi32.lib /link /SUBSYSTEM:WINDOWS /OUT:diag_before.exe
if errorlevel 1 exit /b 1
popd
