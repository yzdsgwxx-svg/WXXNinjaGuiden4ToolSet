from pathlib import Path

root = Path('overlay')

# ---------- index.html (idempotent: the first run already added it) ----------
p = root / 'index.html'
s = p.read_text(encoding='utf-8')
if 'rumble-clear' not in s:
    old = '<output id="rumble-value">0%</output><button id="copy-url">复制直播 URL</button>'
    assert old in s
    s = s.replace(old, old + '<button id="rumble-clear" title="取消震动捕获并清空已选目标程序">清除</button>', 1)
    p.write_text(s, encoding='utf-8')

# ---------- preload.js ----------
p = root / 'preload.js'
s = p.read_text(encoding='utf-8')
if 'rumbleClear' not in s:
    old = "  rumbleInject: pid => ipcRenderer.invoke('rumble-inject', pid)"
    assert old in s
    s = s.replace(old, old + ",\n  rumbleClear: () => ipcRenderer.invoke('rumble-clear')", 1)
    p.write_text(s, encoding='utf-8')

# ---------- main.js ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')
if "ipcMain.handle('rumble-clear'" not in s:
    old = "  ipcMain.on('input-config',"
    assert old in s
    new = """  /* 清除：通知 DLL 停掉 hook、断开共享内存，并把目标程序清空（下拉框由 renderer 复位）。 */
  ipcMain.handle('rumble-clear', () => {
    if (!rumbleSource) return { ok: false, error: rumbleError || '震动捕获模块不可用' };
    const pid = rumbleInfo.injectedPid;
    try {
      if (pid) rumbleSource.setEnabled(pid, false);
      rumbleSource.selectTarget(0);
    } catch (error) { log('rumble clear failed', error?.message || String(error)); }
    rumbleInfo.injectedPid = 0;
    rumbleInfo.message = '已清除';
    log('rumble clear', safeJson({ released: pid }));
    return { ok: true, released: pid };
  });
  ipcMain.on('input-config',"""
    s = s.replace(old, new, 1)

if 'clearTarget' not in s:
    anchor = "      fs.mkdirSync(artifactDir, { recursive: true });\n      fs.writeFileSync(path.join(artifactDir, 'preview.png')"
    assert anchor in s
    check = """      /* 清除按钮：必须解除注入，并把下拉框恢复成未选中。 */
      result.clearTarget = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        const before = select.value;
        document.getElementById('rumble-clear').click();
        await new Promise(r => setTimeout(r, 700));
        const info = await window.desktop.rumbleInfo();
        return { before, after: select.value, injectedPid: info.injectedPid, status: document.getElementById('rumble-status').textContent };
      })()`);
      if (result.clearTarget.before && result.clearTarget.after) result.errors.push('clear did not reset the dropdown');
      if (result.clearTarget.injectedPid) result.errors.push('clear did not detach the injected process');
"""
    s = s.replace(anchor, check + anchor, 1)
p.write_text(s, encoding='utf-8')

# ---------- renderer.js ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')
if "rumble-clear" not in s:
    old = "  rumbleProcess?.addEventListener('change', async () => {"
    assert old in s
    new = """  /* 清除：停掉震动捕获，并把下拉框恢复成「未选中」。 */
  $('rumble-clear')?.addEventListener('click', async () => {
    if (injecting) return;
    try { await window.desktop?.rumbleClear?.(); }
    catch (error) { window.desktop?.log?.('rumble clear failed: ' + (error?.message || error)); }
    if (rumbleProcess) rumbleProcess.value = '';
    if (rumbleStatusLabel) rumbleStatusLabel.textContent = '已清除 · 展开下拉框可重新选择';
  });
""" + old
    s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')
print('overlay: 清除 button wired end to end')
