import re
from pathlib import Path

root = Path('overlay')

# ---------- style.css: no more -webkit-app-region anywhere ----------
p = root / 'style.css'
s = p.read_text(encoding='utf-8')
s = re.sub(r';?-webkit-app-region:[a-z-]+', '', s)
s = s.replace('{;', '{').replace(';;', ';')
assert '-webkit-app-region' not in s
p.write_text(s, encoding='utf-8')

# ---------- preload.js: expose the drag channel ----------
p = root / 'preload.js'
s = p.read_text(encoding='utf-8')
old = "  log: message => ipcRenderer.send('renderer-log', String(message)),"
new = "  startDrag: () => ipcRenderer.send('drag-start'),\n  endDrag: () => ipcRenderer.send('drag-end'),\n" + old
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# ---------- main.js: follow the cursor while dragging (no app-region involved) ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

swap("let win = null, tray = null, closeRequested = false;",
     "let win = null, tray = null, closeRequested = false;\n"
     "/* 拖动窗口：CSS 的 -webkit-app-region 在无边框透明窗口上会吃掉按钮点击（实测 main 一开 drag，\n"
     "   标题栏按钮的 WM_NCHITTEST 就变成 HTCAPTION），所以改成 JS 跟随光标移动窗口。 */\n"
     "let drag = null, dragStartCount = 0, dragEndCount = 0;\n"
     "function endDrag() {\n"
     "  if (!drag) return;\n"
     "  clearInterval(drag.timer);\n"
     "  drag = null;\n"
     "  dragEndCount++;\n"
     "}\n"
     "function startDrag() {\n"
     "  if (drag || !win || win.isDestroyed()) return;\n"
     "  const origin = screen.getCursorScreenPoint();\n"
     "  const from = win.getBounds();\n"
     "  dragStartCount++;\n"
     "  drag = { timer: setInterval(() => {\n"
     "    if (!win || win.isDestroyed()) { endDrag(); return; }\n"
     "    const now = screen.getCursorScreenPoint();\n"
     "    win.setPosition(from.x + (now.x - origin.x), from.y + (now.y - origin.y));\n"
     "  }, 8) };\n"
     "}")

swap("  ipcMain.on('input-config',",
     "  ipcMain.on('drag-start', () => startDrag());\n"
     "  ipcMain.on('drag-end', () => endDrag());\n"
     "  ipcMain.on('input-config',")

# Mouse release outside the window (or over a child view) still has to end the drag.
swap("  win.webContents.on('did-fail-load', (_event, code, description, url) => log('did-fail-load', code, description, url));",
     "  win.webContents.on('did-fail-load', (_event, code, description, url) => log('did-fail-load', code, description, url));\n"
     "  win.hookWindowMessage(0x0202, () => endDrag());  // WM_LBUTTONUP\n"
     "  win.on('blur', () => endDrag());\n"
     "  win.on('minimize', () => endDrag());")

# self-test: canvas press starts a drag, button press must not
swap("      result.dragRegion = await win.webContents.executeJavaScript(",
     """      await win.webContents.executeJavaScript(`(()=>{const r=document.querySelector('main').getBoundingClientRect();const t=document.elementFromPoint(Math.round(r.x+r.width/2),Math.round(r.y+r.height/2));t.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,buttons:1}));})()`);
      await new Promise(resolve => setTimeout(resolve, 250));
      const dragStartedOnCanvas = dragStartCount;
      await win.webContents.executeJavaScript(`window.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0}))`);
      await new Promise(resolve => setTimeout(resolve, 250));
      const dragEndedOnRelease = dragEndCount;
      await win.webContents.executeJavaScript(`document.getElementById('close').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,buttons:1}))`);
      await new Promise(resolve => setTimeout(resolve, 200));
      const dragStartedOnButton = dragStartCount - dragStartedOnCanvas;
      await win.webContents.executeJavaScript(`window.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0}))`);
      result.dragHook = { startedOnCanvas: dragStartedOnCanvas, endedOnRelease: dragEndedOnRelease, startedOnButton: dragStartedOnButton };
      if (dragStartedOnCanvas !== 1 || dragEndedOnRelease !== 1 || dragStartedOnButton !== 0) result.errors.push('window drag hook failed');

      result.dragRegion = await win.webContents.executeJavaScript(""")

# the old assertions were about -webkit-app-region, which no longer exists
old_assert = """      if (result.dragRegion.header !== 'drag' || result.dragRegion.nav !== 'no-drag') result.errors.push('titlebar is not draggable');
      if (result.dragRegion.height < 28) result.errors.push('titlebar too thin to grab');
      /* 需求：整个窗口空白处都能拖动，不只是标题栏。 */
      for (const key of ['main', 'footer', 'aside']) if (result.dragRegion[key] !== 'drag') result.errors.push('window area is not draggable: ' + key);
      for (const key of ['select', 'button']) if (result.dragRegion[key] !== 'no-drag') result.errors.push('control lost its clicks: ' + key);"""
new_assert = """      if (result.dragRegion.height < 28) result.errors.push('titlebar too thin to grab');
      for (const key of Object.keys(result.dragRegion)) if (result.dragRegion[key] === 'drag') result.errors.push('CSS app-region came back: ' + key);"""
assert old_assert in s
s = s.replace(old_assert, new_assert, 1)
p.write_text(s, encoding='utf-8')

# ---------- renderer.js: grab the window from anywhere that is not a control ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')
anchor = "  $('copy-url').onclick=async()=>{"
assert anchor in s
hook = """  /* 窗口拖动：按在非控件区域就开始移动窗口（控件保持正常点击）。 */
  const CONTROL = 'button,select,input,textarea,option,label,a';
  document.addEventListener('pointerdown', event => {
    if (event.button !== 0 || source) return;
    const target = event.target instanceof Element ? event.target : null;
    if (target && target.closest(CONTROL)) return;
    window.desktop?.startDrag?.();
  });
  document.addEventListener('pointerup', () => window.desktop?.endDrag?.());
  window.addEventListener('blur', () => window.desktop?.endDrag?.());

"""
s = s.replace(anchor, hook + anchor, 1)
p.write_text(s, encoding='utf-8')
print('overlay: JS window dragging replaces -webkit-app-region')
