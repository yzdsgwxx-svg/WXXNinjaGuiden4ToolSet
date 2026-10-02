from pathlib import Path

root = Path('overlay')

# ---------- renderer.js ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

swap("""  async function connectTarget(pid, label) {
    if (!pid || injecting) return false;""",
     """  /* 记住上次连上的目标：下次打开覆层优先恢复它，而不是每次都跳回忍龙 4。 */
  const TARGET_KEY = 'rumble-target';
  function rememberTarget(pid, label) {
    try { localStorage.setItem(TARGET_KEY, JSON.stringify({ pid: Number(pid), name: String(label || '') })); } catch {}
  }
  function forgetTarget() { try { localStorage.removeItem(TARGET_KEY); } catch {} }
  function rememberedTarget() {
    try { return JSON.parse(localStorage.getItem(TARGET_KEY) || 'null'); } catch { return null; }
  }
  /* 记忆里的进程还在运行才恢复它（pid 会被系统复用，所以名字也要对得上）。 */
  async function restoreTarget() {
    const saved = rememberedTarget();
    if (!saved || !saved.pid || !rumbleProcess) return false;
    const option = [...rumbleProcess.options].find(item =>
      Number(item.value) === Number(saved.pid) && (!saved.name || item.textContent.startsWith(saved.name)));
    if (!option) { forgetTarget(); return false; }
    rumbleProcess.value = option.value;
    return await connectTarget(Number(option.value), option.textContent);
  }
  async function connectTarget(pid, label) {
    if (!pid || injecting) return false;""")

swap("""      const result = await window.desktop.rumbleInject(pid);
      ok = !!result.ok;
      rumbleStatusLabel.textContent = ok ? `已连接 · ${label}` : `连接失败：${result.error || '未知错误'}`;""",
     """      const result = await window.desktop.rumbleInject(pid);
      ok = !!result.ok;
      if (ok) rememberTarget(pid, label); else forgetTarget();
      rumbleStatusLabel.textContent = ok ? `已连接 · ${label}` : `连接失败：${result.error || '未知错误'}`;""")

swap("""    if (rumbleProcess) rumbleProcess.value = '';
    if (rumbleStatusLabel) rumbleStatusLabel.textContent = '已清除 · 展开下拉框可重新选择';""",
     """    forgetTarget();
    if (rumbleProcess) rumbleProcess.value = '';
    if (rumbleStatusLabel) rumbleStatusLabel.textContent = '已清除 · 展开下拉框可重新选择';""")

swap("""  /* 打开覆层时就先认一遍：刷新进程列表，没选过目标程序就直接连上正在运行的忍龙 4。 */
  if (!source) refreshRumbleProcesses().then(() => { if (!rumbleProcess?.value) autoSelectGame(); });""",
     """  /* 打开覆层时的顺序：先恢复上次记住的目标（它还在运行才行），没有才去找忍龙 4。 */
  if (!source) refreshRumbleProcesses().then(async () => {
    if (rumbleProcess?.value) return;
    if (await restoreTarget()) return;
    if (!rumbleProcess?.value) autoSelectGame();
  });""")
p.write_text(s, encoding='utf-8')

# ---------- main.js: cover remember / forget / stale fallback ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')

def swap2(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

# (a) attached target must be persisted
swap2("""      if (Number(result.autoOnStart.value || 0) !== result.autoOnStart.injectedPid) result.errors.push('overlay did not attach the game on startup');""",
      """      if (Number(result.autoOnStart.value || 0) !== result.autoOnStart.injectedPid) result.errors.push('overlay did not attach the game on startup');
      /* 连上以后必须把目标记下来，下次打开优先恢复它。 */
      result.targetMemory = await win.webContents.executeJavaScript(`(() => ({
        saved: JSON.parse(localStorage.getItem('rumble-target') || 'null'),
        value: document.getElementById('rumble-process').value
      }))()`);
      if (Number(result.targetMemory.saved?.pid || 0) !== Number(result.targetMemory.value || 0)) result.errors.push('attached target was not remembered');""")

# (b) clear must forget it too
swap2("""        return { before, after: select.value, injectedPid: info.injectedPid, status: document.getElementById('rumble-status').textContent };""",
      """        return { before, after: select.value, injectedPid: info.injectedPid, status: document.getElementById('rumble-status').textContent,
          remembered: localStorage.getItem('rumble-target') };""")
swap2("""      if (result.clearTarget.injectedPid) result.errors.push('clear did not detach the injected process');""",
      """      if (result.clearTarget.injectedPid) result.errors.push('clear did not detach the injected process');
      if (result.clearTarget.remembered) result.errors.push('clear did not forget the remembered target');

      /* 记忆里的进程已经不在了：重新打开覆层应回落到忍龙 4，而不是卡在空选择。 */
      await win.webContents.executeJavaScript(`localStorage.setItem('rumble-target', JSON.stringify({ pid: 999999, name: 'ghost.exe' }))`);
      win.webContents.reload();
      await new Promise(resolve => setTimeout(resolve, 2000));
      result.staleMemory = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        for (let i = 0; i < 50 && !select.value; i++) await new Promise(r => setTimeout(r, 100));
        const info = await window.desktop.rumbleInfo();
        return { value: select.value, injectedPid: info.injectedPid, label: select.selectedOptions[0]?.textContent || '' };
      })()`);
      if (!result.staleMemory.value || Number(result.staleMemory.value) !== result.staleMemory.injectedPid) result.errors.push('stale memory blocked the fallback to the game');""")
p.write_text(s, encoding='utf-8')
print('overlay: target memory + self-test coverage')
