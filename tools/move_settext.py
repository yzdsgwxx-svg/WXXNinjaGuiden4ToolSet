from pathlib import Path
p=Path('src/launcher.cpp');s=p.read_text(encoding='utf-8')
a=s.index('/* ---------- 避免每秒重绘 ---------- */')
b=s.index('static void RefreshModState(){',a)
block=s[a:b]
s=s[:a]+s[b:]
anchor='static void RefreshSaveState(){'
assert anchor in s
s=s.replace(anchor,block+anchor,1)
p.write_text(s,encoding='utf-8')
print('moved SetText above first use')
