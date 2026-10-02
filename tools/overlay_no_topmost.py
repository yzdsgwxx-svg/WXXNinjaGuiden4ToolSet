from pathlib import Path

p = Path('overlay/main.js')
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

# 覆层是普通窗口：点别的程序时应该失焦并被盖住，不要永远压在别人上面。
swap("transparent: true, frame: false, alwaysOnTop: true, resizable: true,",
     "transparent: true, frame: false, alwaysOnTop: false, resizable: true,")
swap("  win.setAlwaysOnTop(true, 'screen-saver');\n", "")

# self-test: 不许再置顶
swap("      const windowBounds = win.getBounds();",
     """      result.topmost = { alwaysOnTop: win.isAlwaysOnTop() };
      if (result.topmost.alwaysOnTop) result.errors.push('overlay stays on top of other windows');
      const windowBounds = win.getBounds();""")
p.write_text(s, encoding='utf-8')
print('overlay window is no longer always-on-top')
