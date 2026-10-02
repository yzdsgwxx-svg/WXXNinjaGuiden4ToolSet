"""面板控件访问改为容器感知：GetDlgItem(w/gMain, id) -> Ctl(id)。

滚动容器改造后控件挂在 gScrollBox 上，GetDlgItem(gMain, id) 会拿到 NULL。
只替换控件查找，不动 Ctl() 自身的实现（第 218/219 行）。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\launcher.cpp')
s = p.read_text(encoding='utf-8')

# Ctl() 内部的两行保持原样：先把它们临时挖出来
guard_start = s.index('static HWND Ctl(int id){')
guard_end = s.index('}', s.index('return gMain?GetDlgItem(gMain,id):nullptr;')) + 1
guard = s[guard_start:guard_end]
s = s[:guard_start] + '@@CTL@@' + s[guard_end:]

pairs = [
    ('GetDlgItem(gMain,ID_MOD_LOAD)', 'Ctl(ID_MOD_LOAD)'),
    ('GetDlgItem(w,ID_OVERLAY_OPEN)', 'Ctl(ID_OVERLAY_OPEN)'),
    ('GetDlgItem(w,ID_SWITCH)', 'Ctl(ID_SWITCH)'),
    ('GetDlgItem(w,ID_SWITCH_TOGGLE)', 'Ctl(ID_SWITCH_TOGGLE)'),
    ('GetDlgItem(w,ID_EXITSAVE_TOGGLE)', 'Ctl(ID_EXITSAVE_TOGGLE)'),
]
total = 0
for old, new in pairs:
    n = s.count(old)
    total += n
    s = s.replace(old, new)
    print('%-34s -> %-30s x%d' % (old, new, n))

s = s.replace('@@CTL@@', guard, 1)
assert 'GetDlgItem(gMain,ID_MOD_LOAD)' not in s and 'GetDlgItem(w,ID_' not in s
assert 'static HWND Ctl(int id){' in s
p.write_text(s, encoding='utf-8')
print('replaced', total, 'call sites')
