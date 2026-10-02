@echo off
rem Build RumbleHook.dll (x64). Output: native\bin\RumbleHook.dll
rem Keep this file ASCII-only: cmd.exe parses .bat with the OEM codepage and UTF-8 Chinese breaks it.
setlocal
cd /d "%~dp0"

set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\VC\Auxiliary\Build\vcvarsall.bat"
if not exist "%VCVARS%" (
  echo [build] vcvarsall.bat not found: %VCVARS%
  exit /b 1
)
call "%VCVARS%" x64 >nul
if errorlevel 1 (
  echo [build] vcvarsall x64 failed
  exit /b 1
)

set "MH=..\..\..\third_party\minhook"
if not exist "%MH%\src\hook.c" (
  echo [build] MinHook not found: %MH%
  exit /b 1
)
if not exist "obj" mkdir "obj"
if not exist "..\bin" mkdir "..\bin"

cl /nologo /LD /O2 /MT /EHsc /GS- /utf-8 /D_CRT_SECURE_NO_WARNINGS /D_CRT_NONSTDC_NO_DEPRECATE ^
  rumble_hook.cpp ^
  "%MH%\src\hook.c" "%MH%\src\buffer.c" "%MH%\src\trampoline.c" "%MH%\src\hde\hde64.c" ^
  /I "%MH%\include" /I "%MH%\src" /I "%MH%\src\hde" ^
  /Fo:obj\ /Fd:obj\vc.pdb ^
  /link /OUT:..\bin\RumbleHook.dll /MACHINE:X64 /INCREMENTAL:NO
if errorlevel 1 (
  echo [build] compile failed
  exit /b 1
)
echo [build] RumbleHook.dll OK

if exist "test-target.cpp" (
  cl /nologo /O2 /MT /utf-8 test-target.cpp /Fo:obj\ /Fd:obj\test.pdb ^
    /link /OUT:..\bin\rumble-test.exe xinput.lib /MACHINE:X64 /INCREMENTAL:NO
  if errorlevel 1 (
    echo [build] test target failed
    exit /b 1
  )
  echo [build] rumble-test.exe OK
)
dir /b "..\bin"
endlocal
