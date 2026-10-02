from pathlib import Path
p=Path('build.cmd');s=p.read_text();s=s.replace('cl /nologo /std:c++17 /utf-8 /O2 /MT /W4 /EHsc ..\\src\\launcher.cpp','rc /nologo /fo toolset.res ..\\src\\toolset.rc\nif errorlevel 1 exit /b 1\ncl /nologo /std:c++17 /utf-8 /O2 /MT /W4 /EHsc ..\\src\\launcher.cpp toolset.res').replace('/OUT:..\\dist\\SixSlotLauncher.exe','/OUT:..\\dist\\WXXNinjaGuiden4ToolSet.exe');p.write_text(s)
p=Path('dist/Start.cmd');p.write_text('@echo off\nstart "" "%~dp0WXXNinjaGuiden4ToolSet.exe"\n')
p=Path('dist/Stop.cmd');p.write_text('@echo off\nstart "" "%~dp0WXXNinjaGuiden4ToolSet.exe" --stop\n')
