from pathlib import Path

root = Path('overlay')

# ---------- index.html: 清除 before 复制URL, and shorter label ----------
p = root / 'index.html'
s = p.read_text(encoding='utf-8')
old = '<button id="copy-url">复制直播 URL</button><button id="rumble-clear" title="取消震动捕获并清空已选目标程序">清除</button>'
assert old in s, s[s.index('rumble-row'):s.index('rumble-row') + 400]
s = s.replace(old, '<button id="rumble-clear" title="取消震动捕获并清空已选目标程序">清除</button>'
                   '<button id="copy-url">复制 URL</button>', 1)
assert '复制直播 URL' not in s
p.write_text(s, encoding='utf-8')

# ---------- renderer.js: the label it restores after "已复制" ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')
assert "textContent='复制直播 URL'" in s
s = s.replace("textContent='复制直播 URL'", "textContent='复制 URL'")
assert '复制直播 URL' not in s
p.write_text(s, encoding='utf-8')
print('overlay: 清除 moved left of 复制 URL, label shortened')
