@echo off
rem Build SixSlot.dll only. Use this while the game or the panel holds the other artifacts,
rem so build.cmd does not fail at the exe link step.
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0.."
if not exist build mkdir build
if not exist dist mkdir dist
pushd build
cl /nologo /O2 /MT /W3 /c /I ..\third_party\minhook\include ..\third_party\minhook\src\buffer.c ..\third_party\minhook\src\hook.c ..\third_party\minhook\src\trampoline.c ..\third_party\minhook\src\hde\hde64.c
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /utf-8 /O2 /MT /W4 /EHsc /LD /I ..\third_party\minhook\include ..\src\mod.cpp buffer.obj hook.obj trampoline.obj hde64.obj user32.lib /link /OUT:..\dist\SixSlot.dll
if errorlevel 1 exit /b 1
popd
