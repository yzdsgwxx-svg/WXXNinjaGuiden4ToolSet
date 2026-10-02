from pathlib import Path

p = Path('overlay/main.js')
s = p.read_text(encoding='utf-8')

def swap(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

# ---------- Win32 physical-pixel helpers ----------
swap("let win = null, tray = null, closeRequested = false;",
     """let win = null, tray = null, closeRequested = false;

/* 跨不同缩放率的显示器时，Electron 的 DIP 坐标 + setBounds 会把窗口尺寸改掉
   （实测 880x740 → 副屏 1100x925 → 回主屏 704x592）。窗口拖动全程改用 Win32 物理像素：
   GetCursorPos/GetWindowRect 拿物理值，SetWindowPos 只挪位置（SWP_NOSIZE）不动尺寸。 */
let native = null;
try {
  const koffi = require('koffi');
  const user32 = koffi.load('user32.dll');
  native = {
    GetCursorPos: user32.func('bool __stdcall GetCursorPos(_Out_ int32_t *point)'),
    GetWindowRect: user32.func('bool __stdcall GetWindowRect(uintptr_t hwnd, _Out_ int32_t *rect)'),
    SetWindowPos: user32.func('bool __stdcall SetWindowPos(uintptr_t hwnd, uintptr_t after, int x, int y, int cx, int cy, uint32_t flags)')
  };
  log('native window move ready');
} catch (error) { log('native window move unavailable', error?.message || String(error)); }
const SWP_NOSIZE = 0x0001, SWP_NOZORDER = 0x0004, SWP_NOACTIVATE = 0x0010;
function windowHandle() {
  if (!win || win.isDestroyed()) return 0;
  const buffer = win.getNativeWindowHandle();
  return buffer.length >= 8 ? Number(buffer.readBigUInt64LE(0)) : buffer.readUInt32LE(0);
}
function cursorPhysical() {
  if (native) { const point = [0, 0]; if (native.GetCursorPos(point)) return { x: point[0], y: point[1] }; }
  return screen.dipToScreenPoint(screen.getCursorScreenPoint());
}
function windowPhysical() {
  const rect = [0, 0, 0, 0];
  if (native && native.GetWindowRect(windowHandle(), rect)) return { x: rect[0], y: rect[1], width: rect[2] - rect[0], height: rect[3] - rect[1] };
  const b = screen.dipToScreenRect(win, win.getBounds());
  return { x: b.x, y: b.y, width: b.width, height: b.height };
}
function moveWindowPhysical(x, y) {
  if (native && native.SetWindowPos(windowHandle(), 0, Math.round(x), Math.round(y), 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)) return true;
  if (!win || win.isDestroyed()) return false;
  const dip = screen.screenToDipPoint({ x: Math.round(x), y: Math.round(y) });
  win.setPosition(dip.x, dip.y);
  return true;
}""")

# ---------- drag loop: physical deltas, position only ----------
swap("""  /* 每帧只加「光标增量」，并显式带上当前 DIP 尺寸：
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
  }, 8) };""",
     """  /* 每帧只加「物理像素增量」，并且只挪位置：跨缩放率显示器时尺寸不会被改。 */
  let last = cursorPhysical();
  dragStartCount++;
  drag = { timer: setInterval(() => {
    if (!win || win.isDestroyed()) { endDrag(); return; }
    /* 自检只验证钩子连通，绝不能跟着测试机的真实鼠标搬动窗口。 */
    if (testing) return;
    const now = cursorPhysical();
    const dx = now.x - last.x, dy = now.y - last.y;
    last = now;
    if (!dx && !dy) return;
    const rect = windowPhysical();
    moveWindowPhysical(rect.x + dx, rect.y + dy);
  }, 8) };""")

# ---------- probe: move across screens the same way the drag does ----------
swap("""      const other = screen.getAllDisplays().find(display => display.id !== screen.getPrimaryDisplay().id);
      if (other) {
        const before = win.getBounds();
        win.setBounds({ x: other.workArea.x + 60, y: other.workArea.y + 60, width: before.width, height: before.height });
        await new Promise(resolve => setTimeout(resolve, 1500));
        await writeProbe('probe-other-screen.json');
        win.setBounds(before);
        await new Promise(resolve => setTimeout(resolve, 800));
        await writeProbe('probe-back.json');
      }""",
     """      const other = screen.getAllDisplays().find(display => display.id !== screen.getPrimaryDisplay().id);
      if (other) {
        const before = windowPhysical();
        const target = screen.dipToScreenRect(win, { x: other.workArea.x + 60, y: other.workArea.y + 60, width: 200, height: 200 });
        moveWindowPhysical(target.x, target.y);
        await new Promise(resolve => setTimeout(resolve, 1500));
        await writeProbe('probe-other-screen.json');
        moveWindowPhysical(before.x, before.y);
        await new Promise(resolve => setTimeout(resolve, 800));
        await writeProbe('probe-back.json');
      }""")
p.write_text(s, encoding='utf-8')
print('drag + probe now move the window in physical pixels (position only)')
