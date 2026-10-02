from pathlib import Path

p = Path('overlay/style.css')
s = p.read_text(encoding='utf-8')

old = ("#minimize,#close{font-size:0;width:32px;height:32px;padding:0;border:0;background:transparent;align-self:center;border-radius:6px}\n"
       "#minimize:hover{background:#ffffff0c}#close:hover{background:#b72a40}")
new = ("/* 透明窗口里 background:transparent 的按钮没有可命中像素，鼠标会落到父级拖动区，\n"
       "   导致按钮点不动（WM_NCHITTEST 返回 HTCAPTION）。给它们和标题栏同色的实心底，视觉不变但能收到点击。 */\n"
       "#minimize,#close{font-size:0;width:32px;height:32px;padding:0;border:0;background:#19191f;align-self:center;border-radius:6px}\n"
       "#minimize:hover{background:#2a2a32}#close:hover{background:#b72a40}")
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('style.css: minimize/close got an opaque hit surface')
