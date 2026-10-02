from pathlib import Path
p=Path('overlay/main.js');s=p.read_text(encoding='utf-8')
old="""  drag = { timer: setInterval(() => {
    if (!win || win.isDestroyed()) { endDrag(); return; }
    const now = screen.getCursorScreenPoint();
    win.setPosition(from.x + (now.x - origin.x), from.y + (now.y - origin.y));
  }, 8) };"""
new="""  drag = { timer: setInterval(() => {
    if (!win || win.isDestroyed()) { endDrag(); return; }
    /* 自检只验证钩子连通，绝不能跟着测试机的真实鼠标搬动窗口。 */
    if (testing) return;
    const now = screen.getCursorScreenPoint();
    win.setPosition(from.x + (now.x - origin.x), from.y + (now.y - origin.y));
  }, 8) };"""
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('smoke drag runs dry, no real window movement')
