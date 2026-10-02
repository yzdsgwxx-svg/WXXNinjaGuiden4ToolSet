import sys
from pathlib import Path

targets = [t for t in (sys.argv[1].split(',') if len(sys.argv) > 1 else []) if t]
p = Path('overlay/style.css')
s = p.read_text(encoding='utf-8')
regions = {
    'main': 'main{flex:1;min-height:150px;display:flex;align-items:center;justify-content:center',
    'footer': 'footer{display:flex;align-items:center;gap:8px;font-size:10px;letter-spacing:1px;color:#8d8380;height:24px;flex-shrink:0',
    'aside': 'aside{flex-shrink:0;border:1px solid #493137;background:#17171dee;padding:12px 16px;border-radius:8px;margin-top:5px',
}
for key, anchor in regions.items():
    on = anchor + ';-webkit-app-region:drag}'
    off = anchor + '}'
    if key in targets:
        if on not in s:
            assert off in s, key
            s = s.replace(off, on, 1)
    else:
        if on in s:
            s = s.replace(on, off, 1)
assert '-webkit-app-region:drag}' not in s.split('body{')[1].split('}')[0]
p.write_text(s, encoding='utf-8')
print('drag regions:', targets or ['(none)'])
