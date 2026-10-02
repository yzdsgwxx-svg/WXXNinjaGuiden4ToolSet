from pathlib import Path
p=Path('overlay/main.js');s=p.read_text(encoding='utf-8')
old="    else if (action === 'minimize') win.minimize();\n    else if (action === 'top') win.setAlwaysOnTop(!win.isAlwaysOnTop(), 'screen-saver');\n"
new="    else if (action === 'minimize') win.minimize();\n"
assert old in s
s=s.replace(old,new,1)
assert 'setAlwaysOnTop' not in s
p.write_text(s,encoding='utf-8')
p=Path('overlay/preload.js');s=p.read_text(encoding='utf-8')
old="if (['close', 'minimize', 'top'].includes(name))"
assert old in s
s=s.replace(old,"if (['close', 'minimize'].includes(name))",1)
p.write_text(s,encoding='utf-8')
print('dead top-most action removed')
