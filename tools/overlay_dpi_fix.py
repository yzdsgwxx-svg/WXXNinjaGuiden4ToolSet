from pathlib import Path

p = Path('overlay/main.js')
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

# --- probe: sample repeatedly + report viewport/DPI so a cross-screen move can be compared ---
swap("""  if (probing) {
    setTimeout(async () => {
      try {""",
     """  if (probing) {
    const writeProbe = async () => {
      try {""")
swap("""        fs.mkdirSync(artifactDir, { recursive: true });
        fs.writeFileSync(path.join(artifactDir, 'probe.json'), JSON.stringify({
          bounds: win.getBounds(), innerWidth: await win.webContents.executeJavaScript('window.innerWidth'),
          innerHeight: await win.webContents.executeJavaScript('window.innerHeight'), points
        }, null, 2));
        log('probe written', safeJson(points));
      } catch (error) { log('probe failed', error?.stack || String(error)); }
    }, 2500);
    setTimeout(() => { log('probe finished'); app.quit(); }, 40000);""",
     """        const metrics = await win.webContents.executeJavaScript(`({
          innerWidth: window.innerWidth, innerHeight: window.innerHeight,
          outerWidth: window.outerWidth, outerHeight: window.outerHeight,
          dpr: window.devicePixelRatio, screenX: window.screenX, screenY: window.screenY,
          mediaNarrow: window.matchMedia('(max-width:620px)').matches,
          brandText: getComputedStyle(document.querySelector('.brand span')).display,
          navLeft: Math.round(document.querySelector('nav').getBoundingClientRect().x)
        })`);
        const bounds = win.getBounds();
        const host = screen.getDisplayNearestPoint({ x: bounds.x, y: bounds.y });
        fs.mkdirSync(artifactDir, { recursive: true });
        fs.writeFileSync(path.join(artifactDir, 'probe.json'), JSON.stringify({
          bounds, metrics,
          display: { id: host.id, scaleFactor: host.scaleFactor, bounds: host.bounds, workArea: host.workArea },
          cursor: screen.getCursorScreenPoint(),
          points
        }, null, 2));
        log('probe written', safeJson({ bounds, innerWidth: metrics.innerWidth, dpr: metrics.dpr, scaleFactor: host.scaleFactor }));
      } catch (error) { log('probe failed', error?.stack || String(error)); }
    };
    setTimeout(() => { writeProbe(); setInterval(writeProbe, 1500); }, 2500);
    setTimeout(() => { log('probe finished'); app.quit(); }, 45000);""")

# --- drag: move by per-frame delta and keep the DIP size, so a DPI change cannot compound ---
swap("""function startDrag() {
  if (drag || !win || win.isDestroyed()) return;
  const origin = screen.getCursorScreenPoint();
  const from = win.getBounds();
  dragStartCount++;
  drag = { timer: setInterval(() => {
    if (!win || win.isDestroyed()) { endDrag(); return; }
    /* 自检只验证钩子连通，绝不能跟着测试机的真实鼠标搬动窗口。 */
    if (testing) return;
    const now = screen.getCursorScreenPoint();
    win.setPosition(from.x + (now.x - origin.x), from.y + (now.y - origin.y));
  }, 8) };
}""",
     """function startDrag() {
  if (drag || !win || win.isDestroyed()) return;
  /* 每帧只加「光标增量」，并显式带上当前 DIP 尺寸：
     跨不同缩放率的显示器时，绝对坐标换算是按所在屏算的，用起始位置累加会漂移甚至越拖越大。 */
  let last = screen.getCursorScreenPoint();
  dragStartCount++;
  drag = { timer: setInterval(() => {
    if (!win || win.isDestroyed()) { endDrag(); return; }
    /* 自检只验证钩子连通，绝不能跟着测试机的真实鼠标搬动窗口。 */
    if (testing) return;
    const now = screen.getCursorScreenPoint();
    const dx = now.x - last.x, dy = now.y - last.y;
    last = now;
    if (!dx && !dy) return;
    const bounds = win.getBounds();
    win.setBounds({ x: bounds.x + dx, y: bounds.y + dy, width: bounds.width, height: bounds.height });
  }, 8) };
}""")
p.write_text(s, encoding='utf-8')

# --- narrow-screen breakpoint: only for genuinely tiny windows, not for DPI-shifted ones ---
p = Path('overlay/style.css')
s = p.read_text(encoding='utf-8')
old = "@media(max-width:620px){"
assert old in s
s = s.replace(old, "/* 断点必须低于 minWidth(460)，否则跨 DPI 显示器时视口变窄会误触发移动端布局。 */\n@media(max-width:480px){", 1)
p.write_text(s, encoding='utf-8')
print('probe: repeated sampling + DPI metrics; drag: per-frame delta; breakpoint 620 -> 480')
