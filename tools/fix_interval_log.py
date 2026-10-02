from pathlib import Path
p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')
old = '    Log("Menu re-save interval: %s",menuIntervalMs.load()?std::to_string(menuIntervalMs.load()).append(" ms").c_str():"off (precise triggers only)");'
assert old in s, 'log line not found'
new = ('    if(menuIntervalMs.load())Log("Menu re-save interval: %u ms",menuIntervalMs.load());\n'
       '    else Log("Menu re-save interval: off (precise triggers only)");')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('fixed log line')
