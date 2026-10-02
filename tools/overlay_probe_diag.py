from pathlib import Path

p = Path('overlay/main.js')
s = p.read_text(encoding='utf-8')
old = """        const points = await win.webContents.executeJavaScript(`(()=>{
          const at = id => { const el = document.getElementById(id); if (!el) return null; const r = el.getBoundingClientRect(); return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }; };"""
new = """        const points = await win.webContents.executeJavaScript(`(()=>{
          const at = id => {
            const el = document.getElementById(id); if (!el) return null;
            const r = el.getBoundingClientRect();
            const x = Math.round(r.x + r.width / 2), y = Math.round(r.y + r.height / 2);
            const chain = [];
            for (let node = el; node && node !== document.documentElement; node = node.parentElement) {
              const cs = getComputedStyle(node);
              chain.push((node.id ? '#' + node.id : node.tagName.toLowerCase()) + '=' + (cs.webkitAppRegion || 'none'));
            }
            const top = document.elementFromPoint(x, y);
            return { x, y, hit: top ? (top.id || top.tagName) : null, region: getComputedStyle(el).webkitAppRegion,
              background: getComputedStyle(el).backgroundColor, chain };
          };"""
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('probe: element hit + computed style diagnostics')
