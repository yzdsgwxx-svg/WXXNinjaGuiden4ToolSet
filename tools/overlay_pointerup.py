from pathlib import Path
p=Path('overlay/renderer.js');s=p.read_text(encoding='utf-8')
old="  document.addEventListener('pointerup', () => window.desktop?.endDrag?.());"
new="  /* 挂在 window 上：document 上的 pointerup 会冒泡上来，鼠标在窗口内任何位置松开都能结束拖动。 */\n  window.addEventListener('pointerup', () => window.desktop?.endDrag?.());"
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('pointerup listener moved to window')
