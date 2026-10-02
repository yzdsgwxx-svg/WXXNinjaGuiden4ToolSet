from pathlib import Path

root = Path('overlay')

# ---------- renderer.js: run the same detection when the overlay opens ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')
old = """  /* 目标程序还没选过时，展开下拉框先找忍龙 4：在运行就直接选中并连上，省一次手动点击。 */
  async function autoSelectGame() {"""
new = """  /* 目标程序还没选过时，找忍龙 4：在运行就直接选中并连上，省一次手动点击。
     覆层打开时跑一次，之后每次展开下拉框也跑。 */
  async function autoSelectGame() {"""
assert old in s
s = s.replace(old, new, 1)

old = "  if (!source) refreshRumbleProcesses();"
new = """  /* 打开覆层时就先认一遍：刷新进程列表，没选过目标程序就直接连上正在运行的忍龙 4。 */
  if (!source) refreshRumbleProcesses().then(() => { if (!rumbleProcess?.value) autoSelectGame(); });"""
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# ---------- main.js: cover the startup path in the self-test ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')
anchor = "      win.show(); win.focus();\n      async function clickControl(id) {"
assert anchor in s
check = """      win.show(); win.focus();
      /* 覆层一打开就该自动认到正在运行的忍龙 4（和展开下拉框同一套逻辑）。 */
      result.autoOnStart = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        for (let i = 0; i < 40 && !select.value; i++) await new Promise(r => setTimeout(r, 100));
        const info = await window.desktop.rumbleInfo();
        return { value: select.value, label: select.selectedOptions[0]?.textContent || '', injectedPid: info.injectedPid, status: document.getElementById('rumble-status').textContent };
      })()`);
      if (Number(result.autoOnStart.value || 0) !== result.autoOnStart.injectedPid) result.errors.push('overlay did not attach the game on startup');
      async function clickControl(id) {"""
s = s.replace(anchor, check, 1)
p.write_text(s, encoding='utf-8')
print('overlay: startup also runs the rumble target detection')
