from pathlib import Path

p = Path('overlay/main.js')
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)

swap("const testing = process.argv.includes('--smoke-test');",
     "const testing = process.argv.includes('--smoke-test');\n"
     "/* --probe：只把关键控件的屏幕坐标写出来，供外部用 WM_NCHITTEST 验证“哪块能点、哪块能拖”。 */\n"
     "const probing = process.argv.includes('--probe');")

swap("""} else if (soakMs) {
  /* soak 用独立 profile，避免与正在运行的正式实例抢单实例锁。 */""",
     """} else if (probing) {
  const probeProfile = path.join(artifactDir, 'probe-profile');
  fs.mkdirSync(probeProfile, { recursive: true });
  app.setPath('userData', probeProfile);
} else if (soakMs) {
  /* soak 用独立 profile，避免与正在运行的正式实例抢单实例锁。 */""")

swap("  if (soakMs) setTimeout(() => { log('soak finished', soakMs); app.quit(); }, soakMs);",
     """  if (soakMs) setTimeout(() => { log('soak finished', soakMs); app.quit(); }, soakMs);

  if (probing) {
    setTimeout(async () => {
      try {
        const points = await win.webContents.executeJavaScript(`(()=>{
          const at = id => { const el = document.getElementById(id); if (!el) return null; const r = el.getBoundingClientRect(); return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }; };
          const main = document.querySelector('main').getBoundingClientRect();
          const aside = document.querySelector('aside').getBoundingClientRect();
          return { minimize: at('minimize'), close: at('close'), select: at('rumble-process'), copy: at('copy-url'),
            titlebar: { x: Math.round(window.innerWidth / 2), y: 24 },
            controller: { x: Math.round(main.x + main.width / 2), y: Math.round(main.y + main.height / 2) },
            footer: { x: Math.round(window.innerWidth / 2), y: Math.round(window.innerHeight - 12) },
            asideBlank: { x: Math.round(aside.x + aside.width - 10), y: Math.round(aside.y + aside.height - 10) } };
        })()`);
        fs.mkdirSync(artifactDir, { recursive: true });
        fs.writeFileSync(path.join(artifactDir, 'probe.json'), JSON.stringify({
          bounds: win.getBounds(), innerWidth: await win.webContents.executeJavaScript('window.innerWidth'),
          innerHeight: await win.webContents.executeJavaScript('window.innerHeight'), points
        }, null, 2));
        log('probe written', safeJson(points));
      } catch (error) { log('probe failed', error?.stack || String(error)); }
    }, 2500);
    setTimeout(() => { log('probe finished'); app.quit(); }, 40000);
  }""")
p.write_text(s, encoding='utf-8')
print('main.js: --probe mode added')
