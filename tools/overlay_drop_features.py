import re
from pathlib import Path

root = Path('overlay')

# ---------- index.html: drop the three buttons + the locked hint ----------
p = root / 'index.html'
s = p.read_text(encoding='utf-8')
s = re.sub(r'<button id="(?:settings-toggle|lock|reset-position)"[^>]*>.*?</button>', '', s, flags=re.S)
s = re.sub(r'<span class="locked-hint">.*?</span>', '', s, flags=re.S)
for gone in ('settings-toggle', 'reset-position', 'locked-hint', 'id="lock"'):
    assert gone not in s, gone
p.write_text(s, encoding='utf-8')

# ---------- renderer.js: no toggles to bind ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')
old = ("  $('settings-toggle').onclick=()=>{$('settings').hidden=!$('settings').hidden;};\n"
       "  for(const name of ['lock','minimize','close','reset-position']) $(name).onclick=()=>window.desktop?.action(name);\n"
       "  window.desktop?.onLock(value=>document.body.classList.toggle('locked',value));\n"
       "  window.desktop?.onSettings(()=>{$('settings').hidden=false;});\n")
assert old in s
s = s.replace(old, "  for(const name of ['minimize','close']) $(name).onclick=()=>window.desktop?.action(name);\n")
for gone in ('settings-toggle', "'lock'", 'onLock', 'onSettings', 'reset-position'):
    assert gone not in s, gone
p.write_text(s, encoding='utf-8')

# ---------- preload.js: action whitelist + dropped listeners ----------
p = root / 'preload.js'
s = p.read_text(encoding='utf-8')
s = s.replace("if (['close', 'minimize', 'lock', 'top', 'reset-position'].includes(name))",
              "if (['close', 'minimize', 'top'].includes(name))")
s = s.replace(",\n  onLock: callback => ipcRenderer.on('locked', (_event, value) => callback(value)),\n"
              "  onSettings: callback => ipcRenderer.on('settings', () => callback())", "")
for gone in ('onLock', 'onSettings', "'lock'"):
    assert gone not in s, gone
p.write_text(s, encoding='utf-8')

# ---------- style.css: locked state ----------
p = root / 'style.css'
s = p.read_text(encoding='utf-8')
s = s.replace(".locked-hint{display:none;flex:1;text-align:center;font-size:10px;letter-spacing:2px;color:#ffb3bf;white-space:nowrap;-webkit-app-region:drag}\n", "")
s = s.replace("/* 穿透时保留标题栏，明确告诉用户当前状态和恢复方式。 */\n", "")
s = re.sub(r'body\.locked[^\n]*\n', '', s)
assert 'locked' not in s, [line for line in s.splitlines() if 'locked' in line]
p.write_text(s, encoding='utf-8')

# ---------- main.js ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)

swap('let win = null, tray = null, locked = false, closeRequested = false;',
     'let win = null, tray = null, closeRequested = false;')
swap("""function showWindow() {
  if (!win || win.isDestroyed()) { log('showWindow ignored: no window'); return; }
  setLocked(false);
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
  win.webContents.send('settings');
}
function setLocked(value) {
  locked = Boolean(value);
  log('setLocked', locked);
  if (!win || win.isDestroyed()) return;
  win.setIgnoreMouseEvents(locked, { forward: true });
  win.webContents.send('locked', locked);
}
""", """/* 唤出窗口：托盘双击、单实例第二启动、全局快捷键都走这里。 */
function showWindow() {
  if (!win || win.isDestroyed()) { log('showWindow ignored: no window'); return; }
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}
""")
swap("""function resetPosition() {
  if (!win || win.isDestroyed()) return;
  win.setBounds(primaryBounds());
  log('reset position', win.getBounds());
}
""", "")
swap("log('heartbeat', { locked, pads: padCount,", "log('heartbeat', { pads: padCount,")
swap("""    else if (action === 'minimize') win.minimize();
    else if (action === 'lock') setLocked(!locked);
    else if (action === 'top') win.setAlwaysOnTop(!win.isAlwaysOnTop(), 'screen-saver');
    else if (action === 'reset-position') resetPosition();
""", """    else if (action === 'minimize') win.minimize();
    else if (action === 'top') win.setAlwaysOnTop(!win.isAlwaysOnTop(), 'screen-saver');
""")
swap("""    tray.setToolTip('忍龙 4 · 黑武士 5 Pro');
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: '显示 / 解锁设置', click: showWindow },
      { label: '鼠标穿透', click: () => setLocked(!locked) },
      { label: '重置窗口位置到主屏', click: resetPosition },
      { type: 'separator' },
      { label: '退出', click: () => app.quit() }
    ]));""", """    tray.setToolTip('WXX · 忍龙 4 控制器覆层');
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: '显示窗口', click: showWindow },
      { type: 'separator' },
      { label: '退出', click: () => app.quit() }
    ]));""")
swap("""        if(!document.querySelector('.pressed')) errors.push('demo does not animate');
        document.querySelector('#settings-toggle').click();
        if(!document.querySelector('#settings').hidden) errors.push('settings toggle failed');
        document.querySelector('#settings-toggle').click();
        return {errors, device: document.querySelector('#device').textContent};""",
     """        if(!document.querySelector('.pressed')) errors.push('demo does not animate');
        return {errors, device: document.querySelector('#device').textContent};""")
swap("""      await clickControl('settings-toggle');
      const settingsClicked = await win.webContents.executeJavaScript(`document.getElementById('settings').hidden`);
      await clickControl('settings-toggle');
      await clickControl('lock'); const lockClicked = locked; setLocked(false);
      await clickControl('minimize'); const minimizeClicked = win.isMinimized(); win.restore(); win.focus();
      await clickControl('close');
      result.controls = { settings: settingsClicked, lock: lockClicked, minimize: minimizeClicked, close: closeRequested };""",
     """      await clickControl('minimize'); const minimizeClicked = win.isMinimized(); win.restore(); win.focus();
      await clickControl('close');
      result.controls = { minimize: minimizeClicked, close: closeRequested };""")
swap("""          titlebar: header.id, visible: getComputedStyle(header).visibility, locked: document.body.classList.contains('locked') };""",
     """          titlebar: header.id, visible: getComputedStyle(header).visibility };""")
swap("""      /* 穿透状态也必须留一条能说明情况的标题栏，否则用户会以为窗口没了。 */
      setLocked(true);
      await new Promise(resolve => setTimeout(resolve, 200));
      fs.writeFileSync(path.join(artifactDir, 'locked.png'), (await win.webContents.capturePage()).toPNG());
      result.lockedHeader = await win.webContents.executeJavaScript(`(()=>{const h=document.querySelector('header'),hint=document.querySelector('.locked-hint');return {visible:getComputedStyle(h).visibility,height:h.getBoundingClientRect().height,hint:getComputedStyle(hint).display,text:hint.textContent}})()`);
      if (result.lockedHeader.visible !== 'visible' || result.lockedHeader.hint === 'none') result.errors.push('locked state hides the titlebar');
      setLocked(false);
""", "")

for gone in ('setLocked', 'resetPosition', 'locked', 'settings-toggle', 'reset-position', 'locked-hint', "'lock'"):
    assert gone not in s, (gone, [line.strip() for line in s.splitlines() if gone in line][:4])
p.write_text(s, encoding='utf-8')
print('overlay: reset / settings / lock removed')
