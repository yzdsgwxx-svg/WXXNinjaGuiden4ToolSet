from pathlib import Path

root = Path('overlay')

# ---------- renderer.js: extract connectTarget, auto-pick the game when the list is opened ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')

old_change = """  rumbleProcess?.addEventListener('change', async () => {
    const pid = Number(rumbleProcess.value);
    if (!pid || injecting) return;
    injecting = true; rumbleProcess.disabled = true;
    rumbleStatusLabel.textContent = '正在连接…';
    try {
      const result = await window.desktop.rumbleInject(pid);
      rumbleStatusLabel.textContent = result.ok ? `已连接 · ${rumbleProcess.selectedOptions[0].textContent}` : `连接失败：${result.error || '未知错误'}`;
    } catch (error) { rumbleStatusLabel.textContent = '连接失败：' + error.message; }
    finally { injecting = false; rumbleProcess.disabled = false; }
  });
  if (!source) refreshRumbleProcesses();
"""
new_change = """  async function connectTarget(pid, label) {
    if (!pid || injecting) return false;
    injecting = true; rumbleProcess.disabled = true;
    rumbleStatusLabel.textContent = '正在连接…';
    let ok = false;
    try {
      const result = await window.desktop.rumbleInject(pid);
      ok = !!result.ok;
      rumbleStatusLabel.textContent = ok ? `已连接 · ${label}` : `连接失败：${result.error || '未知错误'}`;
    } catch (error) { rumbleStatusLabel.textContent = '连接失败：' + error.message; }
    finally { injecting = false; rumbleProcess.disabled = false; }
    return ok;
  }
  rumbleProcess?.addEventListener('change', async () => {
    const pid = Number(rumbleProcess.value);
    if (!pid) return;
    await connectTarget(pid, rumbleProcess.selectedOptions[0]?.textContent || String(pid));
  });
  /* 目标程序还没选过时，展开下拉框先找忍龙 4：在运行就直接选中并连上，省一次手动点击。 */
  async function autoSelectGame() {
    if (!window.desktop?.rumbleInject || !rumbleProcess) return false;
    const game = [...rumbleProcess.options].find(option => /NINJAGAIDEN4/i.test(option.textContent));
    if (!game) return false;
    rumbleProcess.value = game.value;
    return await connectTarget(Number(game.value), game.textContent);
  }
  if (!source) refreshRumbleProcesses();
"""
assert old_change in s
s = s.replace(old_change, new_change, 1)

old_open = """    event.preventDefault();
    await refreshRumbleProcesses();
    reopening = true;"""
new_open = """    event.preventDefault();
    await refreshRumbleProcesses();
    /* 还没选中过目标程序时，展开就等于“自动找忍龙 4”；连上了就不用再弹列表。 */
    if (!rumbleProcess.value && await autoSelectGame()) return;
    reopening = true;"""
assert old_open in s
s = s.replace(old_open, new_open, 1)
p.write_text(s, encoding='utf-8')

# ---------- main.js: cover the new behaviour in the self-test ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')
anchor = """      fs.mkdirSync(artifactDir, { recursive: true });
      fs.writeFileSync(path.join(artifactDir, 'preview.png'), (await win.webContents.capturePage()).toPNG());"""
assert anchor in s
check = """      /* 展开震动捕获下拉框时，没选过目标程序应自动选中正在运行的忍龙 4。 */
      result.autoTarget = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        const game = [...select.options].find(option => /NINJAGAIDEN4/i.test(option.textContent));
        if (!game) return { hasGame: false, value: select.value };
        select.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
        await new Promise(r => setTimeout(r, 1500));
        return { hasGame: true, expected: game.value, value: select.value, label: select.selectedOptions[0]?.textContent || '', status: document.getElementById('rumble-status').textContent };
      })()`);
      if (result.autoTarget.hasGame && result.autoTarget.value !== result.autoTarget.expected) result.errors.push('rumble target not auto-selected when the dropdown opens');
"""
s = s.replace(anchor, check + anchor, 1)
p.write_text(s, encoding='utf-8')
print('overlay: auto-select the game when the rumble dropdown opens')
