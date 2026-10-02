from pathlib import Path

p = Path('overlay/style.css')
s = p.read_text(encoding='utf-8')
nl = '\r\n' if '\r\n' in s else '\n'

def swap(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

# nav itself must stay a drag surface: Chromium ignores a no-drag element nested inside
# another no-drag element, so the buttons in nav lost their clicks (WM_NCHITTEST said
# HTCAPTION). Same shape as aside(drag) > select(no-drag), which works.
swap("nav{display:flex;gap:6px;flex-shrink:0;position:relative;z-index:20;-webkit-app-region:no-drag}",
     "nav{display:flex;gap:6px;flex-shrink:0;position:relative;z-index:20}")
swap("nav,nav *{-webkit-app-region:no-drag}", "nav button{-webkit-app-region:no-drag}")
swap("header nav,header nav *{-webkit-app-region:no-drag;pointer-events:auto}",
     "header nav,header nav button{pointer-events:auto}" + nl + "header nav button{-webkit-app-region:no-drag}")
p.write_text(s, encoding='utf-8')
print('style.css: nav is a drag surface again, only its buttons are no-drag')
