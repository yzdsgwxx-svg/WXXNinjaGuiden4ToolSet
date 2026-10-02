@echo off
cd /d "%~dp0.."
call "C:\Program Files\Microsoft Visual Studio\2022\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
call dist\Repair-Permissions.cmd --quiet
if errorlevel 1 exit /b 1
pushd build
rc /nologo /fo toolset.res ..\src\toolset.rc
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /utf-8 /O2 /MT /W4 /EHsc ..\src\launcher.cpp toolset.res user32.lib gdi32.lib advapi32.lib /link /SUBSYSTEM:WINDOWS /OUT:..\dist\WXXNinjaGuiden4ToolSet.exe
if errorlevel 1 exit /b 1
popd
echo PANEL BUILD OK
