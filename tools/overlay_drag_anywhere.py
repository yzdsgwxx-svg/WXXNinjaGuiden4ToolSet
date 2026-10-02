import re
from pathlib import Path

root = Path('overlay')

# ---------- style.css: whole window becomes a drag surface, only real controls keep clicks ----------
p = root / 'style.css'
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)

# body is the drag surface for the whole frameless window.
swap("body{display:flex;flex-direction:column;padding:16px;user-select:none}",
     "/* 整个窗口都是拖动面：只有下面显式 no-drag 的控件保持可点击。 */\n"
     "body{display:flex;flex-direction:column;padding:16px;user-select:none;-webkit-app-region:drag}")

# main / aside / footer must inherit the drag surface instead of opting out.
swap("main{flex:1;min-height:150px;display:flex;align-items:center;justify-content:center;-webkit-app-region:no-drag}",
     "main{flex:1;min-height:150px;display:flex;align-items:center;justify-content:center}")
swap("aside{flex-shrink:0;border:1px solid #493137;background:#17171dee;padding:12px 16px;border-radius:8px;margin-top:5px;-webkit-app-region:no-drag}",
     "aside{flex-shrink:0;border:1px solid #493137;background:#17171dee;padding:12px 16px;border-radius:8px;margin-top:5px}")

# Only interactive controls are no-drag now (was: the whole aside).
swap("nav,nav button,aside,aside *{-webkit-app-region:no-drag}",
     "nav,nav *{-webkit-app-region:no-drag}\n"
     "aside select,aside button,aside input,aside textarea{-webkit-app-region:no-drag}")
p.write_text(s, encoding='utf-8')

# ---------- main.js: assert the new drag map in the self-test ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')
old = """      result.dragRegion = await win.webContents.executeJavaScript(`(()=>{
        const region = el => el ? getComputedStyle(el).webkitAppRegion : null;
        const header = document.querySelector('header'), nav = document.querySelector('nav'), main = document.querySelector('main');
        const rect = header.getBoundingClientRect();
        return { header: region(header), nav: region(nav), main: region(main), height: rect.height, width: rect.width,
          titlebar: header.id, visible: getComputedStyle(header).visibility };
      })()`);
      if (result.dragRegion.header !== 'drag' || result.dragRegion.nav !== 'no-drag') result.errors.push('titlebar is not draggable');
      if (result.dragRegion.height < 28) result.errors.push('titlebar too thin to grab');"""
new = """      result.dragRegion = await win.webContents.executeJavaScript(`(()=>{
        const region = el => el ? getComputedStyle(el).webkitAppRegion : null;
        const pick = id => document.getElementById(id);
        const header = document.querySelector('header'), nav = document.querySelector('nav');
        const rect = header.getBoundingClientRect();
        return { header: region(header), nav: region(nav), main: region(document.querySelector('main')),
          footer: region(document.querySelector('footer')), aside: region(document.querySelector('aside')),
          select: region(pick('rumble-process')), button: region(pick('copy-url')),
          height: rect.height, width: rect.width, titlebar: header.id, visible: getComputedStyle(header).visibility };
      })()`);
      if (result.dragRegion.header !== 'drag' || result.dragRegion.nav !== 'no-drag') result.errors.push('titlebar is not draggable');
      if (result.dragRegion.height < 28) result.errors.push('titlebar too thin to grab');
      /* 需求：整个窗口空白处都能拖动，不只是标题栏。 */
      for (const key of ['main', 'footer', 'aside']) if (result.dragRegion[key] !== 'drag') result.errors.push('window area is not draggable: ' + key);
      for (const key of ['select', 'button']) if (result.dragRegion[key] !== 'no-drag') result.errors.push('control lost its clicks: ' + key);"""
assert old in s
s = s.replace(old, new, 1)

# Best-effort: synthesise a drag inside main and see whether the window follows.
anchor = """      const windowBounds = win.getBounds();"""
assert anchor in s
probe = """      /* 合成一次拖动（不动真实鼠标）：窗口跟着移动就说明 main 区确实能拖。 */
      const dragBefore = win.getBounds();
      const grab = await win.webContents.executeJavaScript(`(()=>{const r=document.querySelector('main').getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()`);
      win.webContents.sendInputEvent({ type: 'mouseDown', button: 'left', clickCount: 1, x: grab.x, y: grab.y });
      win.webContents.sendInputEvent({ type: 'mouseMove', button: 'left', x: grab.x + 70, y: grab.y + 50 });
      win.webContents.sendInputEvent({ type: 'mouseUp', button: 'left', x: grab.x + 70, y: grab.y + 50 });
      await new Promise(resolve => setTimeout(resolve, 400));
      const dragAfter = win.getBounds();
      result.dragMain = { before: dragBefore, after: dragAfter, moved: dragBefore.x !== dragAfter.x || dragBefore.y !== dragAfter.y };
      win.setBounds(dragBefore);
      await new Promise(resolve => setTimeout(resolve, 200));
"""
s = s.replace(anchor, probe + anchor, 1)
p.write_text(s, encoding='utf-8')
print('overlay: whole window draggable')
