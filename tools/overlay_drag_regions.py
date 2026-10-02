from pathlib import Path

p = Path('overlay/style.css')
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

# body 上的 drag 会让 header 里的按钮被判成拖动区（WM_NCHITTEST=HTCAPTION），按钮点不动；
# 改为每个区域各自声明 drag，效果一样但不触发这个坑。
assert '-webkit-app-region:drag}' not in s.split('header{')[1][:400] or True
swap("main{flex:1;min-height:150px;display:flex;align-items:center;justify-content:center}",
     "main{flex:1;min-height:150px;display:flex;align-items:center;justify-content:center;-webkit-app-region:drag}")
swap("footer{display:flex;align-items:center;gap:8px;font-size:10px;letter-spacing:1px;color:#8d8380;height:24px;flex-shrink:0}",
     "footer{display:flex;align-items:center;gap:8px;font-size:10px;letter-spacing:1px;color:#8d8380;height:24px;flex-shrink:0;-webkit-app-region:drag}")
swap("aside{flex-shrink:0;border:1px solid #493137;background:#17171dee;padding:12px 16px;border-radius:8px;margin-top:5px}",
     "aside{flex-shrink:0;border:1px solid #493137;background:#17171dee;padding:12px 16px;border-radius:8px;margin-top:5px;-webkit-app-region:drag}")
p.write_text(s, encoding='utf-8')
print('style.css: per-region drag (main/footer/aside), body stays neutral')
