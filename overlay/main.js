const { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, nativeImage, screen, clipboard, dialog, crashReporter } = require('electron');
const path = require('node:path');
const fs = require('node:fs');

/* 控制台/管道断开时 stdout、stderr 会异步 emit 'error'（EPIPE），try/catch 抓不到。没有监听器时
   EventEmitter 直接把它抛成未捕获异常；如果异常处理器再去写同一路 stdout，就会变成无限递归刷日志。
   必须在任何输出之前装好空监听器。打包版没有控制台，Electron 内部写 stderr 时同样会走到这里。 */
for (const stream of [process.stdout, process.stderr]) {
  try { stream?.on('error', () => {}); } catch {}
}

const testing = process.argv.includes('--smoke-test');
/* --probe：只把关键控件的屏幕坐标写出来，供外部用 WM_NCHITTEST 验证“哪块能点、哪块能拖”。 */
const probing = process.argv.includes('--probe');
const soakArg = process.argv.find(argument => argument.startsWith('--soak'));
const soakMs = soakArg ? Number(soakArg.split('=')[1] || 60000) : 0;
const artifactDir = app.isPackaged ? path.join(app.getPath('temp'), 'NinjaOverlaySmoke') : path.join(__dirname, 'artifacts');
if (testing) {
  const testProfile = path.join(artifactDir, 'smoke-profile');
  fs.mkdirSync(testProfile, { recursive: true });
  app.setPath('userData', testProfile);
} else if (probing) {
  const probeProfile = path.join(artifactDir, 'probe-profile');
  fs.mkdirSync(probeProfile, { recursive: true });
  app.setPath('userData', probeProfile);
} else if (soakMs) {
  /* soak 用独立 profile，避免与正在运行的正式实例抢单实例锁。 */
  const soakProfile = path.join(artifactDir, 'soak-profile');
  fs.mkdirSync(soakProfile, { recursive: true });
  app.setPath('userData', soakProfile);
}

/* 日志：任何异常都留证据，方便下一轮排查。开发模式同时输出到控制台。 */
const logDir = path.join(app.getPath('userData'), 'logs');
const logPath = path.join(logDir, 'main.log');
let logReady = false, logLines = 0;
function safeJson(value) { try { return JSON.stringify(value); } catch { return String(value); } }
function log(...parts) {
  const line = `[${new Date().toISOString()}] ${parts.map(part => typeof part === 'string' ? part : safeJson(part)).join(' ')}`;
  if (!app.isPackaged) { try { process.stdout.write(line + '\n'); } catch {} }
  try {
    if (!logReady) {
      fs.mkdirSync(logDir, { recursive: true });
      if (fs.existsSync(logPath) && fs.statSync(logPath).size > 2 * 1024 * 1024) fs.renameSync(logPath, logPath + '.1');
      logReady = true;
    }
    fs.appendFileSync(logPath, line + '\n');
    if (++logLines % 4000 === 0 && fs.statSync(logPath).size > 4 * 1024 * 1024) { fs.renameSync(logPath, logPath + '.1'); logLines = 0; }
  } catch {}
}
/* 异常处理器本身绝不能再抛异常，并且要限流，否则一次持续故障会把日志刷到几百 MB。 */
let fatalWindow = 0, fatalCount = 0;
function reportFatal(kind, detail) {
  const now = Date.now();
  if (now - fatalWindow > 60000) { fatalWindow = now; fatalCount = 0; }
  if (fatalCount++ >= 10) return;
  try { log(kind, detail); } catch {}
}
process.on('uncaughtException', error => reportFatal('FATAL uncaughtException', error?.stack || String(error)));
process.on('unhandledRejection', reason => reportFatal('FATAL unhandledRejection', reason?.stack || safeJson(reason)));
process.on('exit', code => log('process exit', code));
app.on('before-quit', () => log('before-quit'));
/* 原生崩溃（koffi / GameInput / GPU 等）不会走 JS 异常，只有 crashpad 能证明。 */
try {
  crashReporter.start({ productName: 'NinjaGuiden4ControllerOverlay', companyName: 'local', submitURL: 'http://127.0.0.1:1/submit', uploadToServer: false, compress: true, rateLimit: false });
  log('crashReporter started', path.join(app.getPath('userData'), 'Crashpad'));
} catch (error) { log('crashReporter failed', error.message); }

let win = null, tray = null, closeRequested = false;

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
}
/* 拖动窗口：CSS 的 -webkit-app-region 在无边框透明窗口上会吃掉按钮点击（实测 main 一开 drag，
   标题栏按钮的 WM_NCHITTEST 就变成 HTCAPTION），所以改成 JS 跟随光标移动窗口。 */
let drag = null, dragStartCount = 0, dragEndCount = 0;
function endDrag() {
  if (!drag) return;
  clearInterval(drag.timer);
  drag = null;
  dragEndCount++;
}
function startDrag() {
  if (drag || !win || win.isDestroyed()) return;
  /* 每帧只加「物理像素增量」，并且只挪位置：跨缩放率显示器时尺寸不会被改。 */
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
  }, 8) };
}

app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.commandLine.appendSwitch('disable-background-timer-throttling');

log('=== start ===', app.getVersion(), { packaged: app.isPackaged, testing, soakMs, electron: process.versions.electron, argv: process.argv.slice(1) });

/* 唤出窗口：托盘双击、单实例第二启动、全局快捷键都走这里。 */
function showWindow() {
  if (!win || win.isDestroyed()) { log('showWindow ignored: no window'); return; }
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}
function primaryBounds() {
  const area = screen.getPrimaryDisplay().workArea;
  const width = Math.min(880, area.width), height = Math.min(740, area.height);
  return { x: area.x + Math.round((area.width - width) / 2), y: area.y + Math.round((area.height - height) / 2), width, height };
}
function overlaps(a, b) {
  const width = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const height = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return width >= 120 && height >= 60;
}
/* 保存的位置必须在某块屏幕上有足够可见区域，否则窗口会“消失”。 */
function restoreBounds() {
  let saved = null;
  try { saved = JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'window.json'), 'utf8')); } catch { saved = null; }
  if (!saved || ![saved.x, saved.y, saved.width, saved.height].every(Number.isFinite)) return primaryBounds();
  const host = screen.getAllDisplays().find(display => overlaps(saved, display.workArea));
  if (!host) { log('saved window position is off-screen, using default', saved); return primaryBounds(); }
  const area = host.workArea;
  const width = Math.min(Math.max(saved.width, 460), area.width);
  const height = Math.min(Math.max(saved.height, 320), area.height);
  return {
    x: Math.min(Math.max(saved.x, area.x), area.x + area.width - width),
    y: Math.min(Math.max(saved.y, area.y), area.y + area.height - height),
    width, height
  };
}
function saveBounds() {
  if (!win || win.isDestroyed()) return;
  try { fs.writeFileSync(path.join(app.getPath('userData'), 'window.json'), JSON.stringify(win.getBounds())); }
  catch (error) { log('save bounds failed', error.message); }
}
function windowState() {
  try {
    if (!win || win.isDestroyed()) return null;
    return { visible: win.isVisible(), minimized: win.isMinimized(), focused: win.isFocused(), bounds: win.getBounds() };
  } catch (error) { return 'state error: ' + error.message; }
}

const gotLock = app.requestSingleInstanceLock();
log('single instance lock', gotLock);
if (!gotLock) { log('another instance is running, exiting'); app.quit(); }
else {
  app.on('second-instance', (_event, argv) => { if (argv.includes('--close')) app.quit(); else showWindow(); });
  if (process.argv.includes('--close')) app.quit();
  else app.whenReady()
    .then(create)
    .catch(error => { log('FATAL create failed', error?.stack || String(error)); if (!testing) dialog.showErrorBox('启动失败', String(error?.message || error)); app.quit(); });
}
app.on('render-process-gone', (_event, contents, details) => {
  log('render-process-gone', safeJson(details));
  if (!testing && contents && !contents.isDestroyed()) { try { contents.reload(); } catch (error) { log('reload failed', error.message); } }
});
app.on('child-process-gone', (_event, details) => log('child-process-gone', safeJson(details)));
app.on('will-quit', () => { log('will-quit'); globalShortcut.unregisterAll(); });
app.on('quit', (_event, exitCode) => log('quit event', exitCode));
app.on('window-all-closed', () => { log('window-all-closed'); app.quit(); });

async function create() {
  for (const event of ['display-added', 'display-removed', 'display-metrics-changed']) {
    screen.on(event, (...args) => log('screen:' + event, safeJson(args.slice(1))));
  }
  let relay;
  const ports = testing ? [0] : [17845, 17855, 17865, 0];
  for (const port of ports) {
    try { relay = await require('./server').startServer(port); break; }
    catch (error) { log('server start failed on port', port, error.message); }
  }
  if (!relay) {
    /* 自动化跑 smoketest 时不能弹阻塞对话框，否则没人点确定就会挂死。 */
    if (!testing) dialog.showErrorBox('直播 URL 启动失败', '本机端口全部占用，无法启动内置服务。请关闭占用端口的程序后重试。');
    app.quit();
    return;
  }
  log('server listening on', relay.port);
  const sourceUrl = `http://127.0.0.1:${relay.port}/overlay`;
  const { makeFrame } = require('./native-input');
  const { createGameInputReader } = require('./gameinput-reader');
  /* 震动捕获（方案A）：注入 RumbleHook.dll 到游戏进程，再从共享内存读回游戏写入的马达强度。 */
  let rumbleSource = null, rumbleError = '';
  try { rumbleSource = require('./rumble-source'); }
  catch (error) { rumbleError = error.message; log('rumble-source require failed', rumbleError); }
  /* 打包后 DLL 由 --extra-resource 放到 resources 根目录：asar 内的文件无法被目标进程 LoadLibrary。 */
  const rumbleDll = app.isPackaged
    ? path.join(process.resourcesPath, 'RumbleHook.dll')
    : path.join(__dirname, 'native', 'bin', 'RumbleHook.dll');
  const rumbleInfo = { injectedPid: 0, message: rumbleError || '未注入' };
  app.on('before-quit', () => { if (rumbleSource && rumbleInfo.injectedPid) rumbleSource.setEnabled(rumbleInfo.injectedPid, false); });
  /* 游戏停止震动或退出后会残留最后一次数值，超过 600ms 没有新写入就归零。 */
  function captureRumble(demoValue) {
    if (inputConfig.demo) return demoValue;
    if (!rumbleSource) return 0;
    const reading = rumbleSource.readRumble();
    return (reading.ok && reading.ageMs <= 600) ? reading.strength : 0;
  }
  let inputConfig = { device: 'auto', deadzone: 8, opacity: 100, extras: true, mapping: { C: 17, Z: 18 }, demo: false };
  let readPads, inputError = '', backendName = '';
  try {
    const backend = require('./input-backend').createBackend({gameInput:createGameInputReader, xInput:require('./native-input').createReader, log, forceXInput:process.argv.includes('--force-xinput')});
    readPads = backend.read; backendName = backend.name;
    log('input backend', backendName);
  }
  catch (error) { log('gameinput init failed', error?.stack || String(error)); inputError = '后台输入初始化失败：' + error.message; readPads = () => []; }
  const closeReader = readPads.close;
  let frameErrors = 0, publishCount = 0, padCount = 0, padSignature = '';
  const inputTimer = setInterval(() => {
    try {
      const pads = readPads();
      const signature = pads.map(pad => pad.id).join('|');
      if (signature !== padSignature) { padSignature = signature; padCount = pads.length; log('pads changed', pads.length, signature); }
      publishCount++;
      const frame = makeFrame(pads, inputConfig, Date.now() / 1000, inputError);
      frame.rumble = captureRumble(frame.rumble);
      relay.publish(frame);
    }
    catch (error) {
      if (frameErrors++ < 5) log('frame error', error?.stack || String(error));
      try { relay.publish(makeFrame([], inputConfig, Date.now() / 1000, '后台输入读取失败：' + error.message)); } catch {}
    }
  }, 16);
  /* 心跳：卡死/闪退时能看出最后活着的时间和状态。 */
  const heartbeat = setInterval(() => log('heartbeat', { pads: padCount, frames: publishCount, errors: frameErrors, rss: Math.round(process.memoryUsage().rss / 1048576) + 'MB', window: windowState() }), 3000);
  app.once('will-quit', () => {
    clearInterval(inputTimer);
    clearInterval(heartbeat);
    try { closeReader?.(); } catch (error) { log('closeReader failed', error.message); }
  });

  ipcMain.handle('source-url', () => sourceUrl);
  ipcMain.handle('rumble-info', () => ({
    supported: !!rumbleSource && rumbleSource.isSupported(),
    dll: rumbleDll,
    injectedPid: rumbleInfo.injectedPid,
    message: rumbleInfo.message,
    reading: rumbleSource ? rumbleSource.readRumble() : { ok: false, reason: rumbleError }
  }));
  ipcMain.handle('rumble-processes', () => {
    if (!rumbleSource) return [];
    try { return rumbleSource.listProcesses().filter(item => /\.exe$/i.test(item.name || '')).sort((a, b) => a.name.localeCompare(b.name)); }
    catch (error) { log('rumble list failed', error.message); return []; }
  });
  ipcMain.handle('rumble-inject', (_event, pid) => {
    if (!rumbleSource) return { ok: false, error: rumbleError || '震动捕获模块不可用' };
    const target = Number(pid);
    if (rumbleInfo.injectedPid && rumbleInfo.injectedPid !== target) rumbleSource.setEnabled(rumbleInfo.injectedPid, false);
    const result = rumbleSource.injectDll(target, rumbleDll);
    if (result.ok) rumbleSource.selectTarget(target);
    rumbleInfo.injectedPid = result.ok ? target : 0;
    rumbleInfo.message = result.ok ? `已注入 ${target}` : (result.error || '注入失败');
    log('rumble inject', safeJson({ pid: target, ok: result.ok, error: result.error || '' }));
    return result;
  });
  ipcMain.on('drag-start', () => startDrag());
  ipcMain.on('drag-end', () => endDrag());
  /* 清除：通知 DLL 停掉 hook、断开共享内存，并把目标程序清空（下拉框由 renderer 复位）。 */
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
  ipcMain.on('input-config', (_event, config) => { if (config && typeof config === 'object') inputConfig = { ...inputConfig, ...config }; });
  ipcMain.on('copy-url', () => { try { clipboard.writeText(sourceUrl); } catch (error) { log('clipboard failed', error.message); } });
  ipcMain.on('renderer-log', (_event, message) => log('renderer', String(message)));

  log('displays', screen.getAllDisplays().map(display => ({ id: display.id, primary: display.id === screen.getPrimaryDisplay().id, workArea: display.workArea, scaleFactor: display.scaleFactor })));
  const bounds = restoreBounds();
  log('window bounds', bounds);
  win = new BrowserWindow({
    icon: path.join(__dirname, 'overlay.ico'), ...bounds, minWidth: 460, minHeight: 320, transparent: true, frame: false, alwaysOnTop: false, resizable: true,
    backgroundColor: '#00000000', show: !testing && !soakMs,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true, backgroundThrottling: false }
  });
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', event => event.preventDefault());
  win.webContents.on('unresponsive', () => log('renderer unresponsive'));
  win.webContents.on('responsive', () => log('renderer responsive'));
  win.webContents.on('preload-error', (_event, preloadPath, error) => log('preload-error', preloadPath, error?.stack || String(error)));
  win.webContents.on('did-fail-load', (_event, code, description, url) => log('did-fail-load', code, description, url));
  win.hookWindowMessage(0x0202, () => endDrag());  // WM_LBUTTONUP
  win.on('blur', () => endDrag());
  win.on('minimize', () => endDrag());

  ipcMain.on('window-action', (_event, action) => {
    log('window-action', action);
    if (!win || win.isDestroyed()) return;
    if (action === 'close') { if (testing) closeRequested = true; else app.quit(); }
    else if (action === 'minimize') win.minimize();
  });
  for (const accelerator of ['Control+Shift+O', 'Control+Alt+O']) {
    try { globalShortcut.register(accelerator, showWindow); log('shortcut registered', accelerator); }
    catch (error) { log('shortcut failed', accelerator, error.message); }
  }
  try {
    const icon = nativeImage.createFromPath(path.join(__dirname, 'overlay.ico'));
    tray = new Tray(icon);
    tray.setToolTip('WXX · 忍龙 4 控制器覆层');
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: '显示窗口', click: showWindow },
      { type: 'separator' },
      { label: '退出', click: () => app.quit() }
    ]));
    tray.on('double-click', showWindow);
  } catch (error) { log('tray init failed', error?.stack || String(error)); tray = null; }

  /* 拖动/缩放后立刻落盘，进程被强杀也不会丢失窗口位置。 */
  let saveTimer = null;
  const scheduleSave = () => { clearTimeout(saveTimer); saveTimer = setTimeout(saveBounds, 800); };
  win.on('move', scheduleSave);
  win.on('resize', scheduleSave);
  win.on('minimize', () => log('window minimize'));
  win.on('restore', () => log('window restore'));
  win.on('hide', () => log('window hide'));
  win.on('show', () => log('window show'));
  win.on('close', () => { log('window close'); clearTimeout(saveTimer); saveBounds(); });
  win.on('closed', () => { log('window closed'); win = null; });
  try { await win.loadURL(`http://127.0.0.1:${relay.port}/`); }
  catch (error) {
    log('loadURL failed', error?.stack || String(error));
    if (!testing) dialog.showErrorBox('界面加载失败', '无法加载本地界面：' + (error?.message || error) + '\n可尝试重新启动本软件。');
  }
  if (soakMs) setTimeout(() => { log('soak finished', soakMs); app.quit(); }, soakMs);

  if (probing) {
    const writeProbe = async (name) => {
      try {
        const points = await win.webContents.executeJavaScript(`(()=>{
          const at = id => {
            const el = document.getElementById(id); if (!el) return null;
            const r = el.getBoundingClientRect();
            const x = Math.round(r.x + r.width / 2), y = Math.round(r.y + r.height / 2);
            const chain = [];
            for (let node = el; node && node !== document.documentElement; node = node.parentElement) {
              const cs = getComputedStyle(node);
              chain.push((node.id ? '#' + node.id : node.tagName.toLowerCase()) + '=' + (cs.webkitAppRegion || 'none'));
            }
            const top = document.elementFromPoint(x, y);
            return { x, y, hit: top ? (top.id || top.tagName) : null, region: getComputedStyle(el).webkitAppRegion,
              background: getComputedStyle(el).backgroundColor, chain };
          };
          const main = document.querySelector('main').getBoundingClientRect();
          const aside = document.querySelector('aside').getBoundingClientRect();
          return { minimize: at('minimize'), close: at('close'), select: at('rumble-process'), copy: at('copy-url'),
            titlebar: { x: Math.round(window.innerWidth / 2), y: 24 },
            controller: { x: Math.round(main.x + main.width / 2), y: Math.round(main.y + main.height / 2) },
            footer: { x: Math.round(window.innerWidth / 2), y: Math.round(window.innerHeight - 12) },
            asideBlank: { x: Math.round(aside.x + aside.width - 10), y: Math.round(aside.y + aside.height - 10) } };
        })()`);
        const metrics = await win.webContents.executeJavaScript(`({
          innerWidth: window.innerWidth, innerHeight: window.innerHeight,
          outerWidth: window.outerWidth, outerHeight: window.outerHeight,
          dpr: window.devicePixelRatio, screenX: window.screenX, screenY: window.screenY,
          mediaNarrow: window.matchMedia('(max-width:480px)').matches,
          brandText: getComputedStyle(document.querySelector('.brand span')).display,
          navLeft: Math.round(document.querySelector('nav').getBoundingClientRect().x)
        })`);
        const bounds = win.getBounds();
        const host = screen.getDisplayNearestPoint({ x: bounds.x, y: bounds.y });
        fs.mkdirSync(artifactDir, { recursive: true });
        fs.writeFileSync(path.join(artifactDir, name), JSON.stringify({
          bounds, metrics,
          display: { id: host.id, scaleFactor: host.scaleFactor, bounds: host.bounds, workArea: host.workArea },
          cursor: screen.getCursorScreenPoint(),
          points
        }, null, 2));
        log('probe written', safeJson({ name, bounds, innerWidth: metrics.innerWidth, dpr: metrics.dpr, scaleFactor: host.scaleFactor }));
      } catch (error) { log('probe failed', error?.stack || String(error)); }
    };
    /* 跨屏 DPI 自检：先在当前屏采样，再把窗口搬到另一块屏采样，最后对比视口/缩放。 */
    setTimeout(async () => {
      await writeProbe('probe.json');
      const other = screen.getAllDisplays().find(display => display.id !== screen.getPrimaryDisplay().id);
      if (other) {
        const before = windowPhysical();
        const target = screen.dipToScreenRect(win, { x: other.workArea.x + 60, y: other.workArea.y + 60, width: 200, height: 200 });
        moveWindowPhysical(target.x, target.y);
        await new Promise(resolve => setTimeout(resolve, 1500));
        await writeProbe('probe-other-screen.json');
        moveWindowPhysical(before.x, before.y);
        await new Promise(resolve => setTimeout(resolve, 800));
        await writeProbe('probe-back.json');
      }
      log('probe finished');
      app.quit();
    }, 2500);
  }

  if (testing) {
    try {
      await new Promise(resolve => setTimeout(resolve, 1200));
      inputConfig.demo = true;
      const result = await win.webContents.executeJavaScript(`(async () => {
        const errors = [];
        if(document.querySelectorAll('[data-button]').length < 19) errors.push('missing buttons');
        
        await new Promise(r => setTimeout(r, 150));
        if(!document.querySelector('.pressed')) errors.push('demo does not animate');
        return {errors, device: document.querySelector('#device').textContent};
      })()`);
      win.show(); win.focus();
      /* 覆层一打开就该自动认到正在运行的忍龙 4（和展开下拉框同一套逻辑）。 */
      result.autoOnStart = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        for (let i = 0; i < 40 && !select.value; i++) await new Promise(r => setTimeout(r, 100));
        const info = await window.desktop.rumbleInfo();
        return { value: select.value, label: select.selectedOptions[0]?.textContent || '', injectedPid: info.injectedPid, status: document.getElementById('rumble-status').textContent };
      })()`);
      if (Number(result.autoOnStart.value || 0) !== result.autoOnStart.injectedPid) result.errors.push('overlay did not attach the game on startup');
      /* 连上以后必须把目标记下来，下次打开优先恢复它。 */
      result.targetMemory = await win.webContents.executeJavaScript(`(() => ({
        saved: JSON.parse(localStorage.getItem('rumble-target') || 'null'),
        value: document.getElementById('rumble-process').value
      }))()`);
      if (Number(result.targetMemory.saved?.pid || 0) !== Number(result.targetMemory.value || 0)) result.errors.push('attached target was not remembered');
      async function clickControl(id) {
        const rect = await win.webContents.executeJavaScript(`(()=>{const r=document.getElementById('${id}').getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()`);
        win.webContents.sendInputEvent({ type: 'mouseDown', button: 'left', clickCount: 1, ...rect });
        win.webContents.sendInputEvent({ type: 'mouseUp', button: 'left', clickCount: 1, ...rect });
        await new Promise(r => setTimeout(r, 150));
      }
      await clickControl('minimize'); const minimizeClicked = win.isMinimized(); win.restore(); win.focus();
      await clickControl('close');
      result.controls = { minimize: minimizeClicked, close: closeRequested };
      if (Object.values(result.controls).some(value => !value)) result.errors.push('mouse control click failed');
      /* 标题栏必须整条可拖动，按钮必须能收到鼠标事件。 */
      await win.webContents.executeJavaScript(`(()=>{const r=document.querySelector('main').getBoundingClientRect();const t=document.elementFromPoint(Math.round(r.x+r.width/2),Math.round(r.y+r.height/2));t.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,buttons:1}));})()`);
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

      result.dragRegion = await win.webContents.executeJavaScript(`(()=>{
        const region = el => el ? getComputedStyle(el).webkitAppRegion : null;
        const pick = id => document.getElementById(id);
        const header = document.querySelector('header'), nav = document.querySelector('nav');
        const rect = header.getBoundingClientRect();
        return { header: region(header), nav: region(nav), main: region(document.querySelector('main')),
          footer: region(document.querySelector('footer')), aside: region(document.querySelector('aside')),
          select: region(pick('rumble-process')), button: region(pick('copy-url')),
          height: rect.height, width: rect.width, titlebar: header.id, visible: getComputedStyle(header).visibility };
      })()`);
      if (result.dragRegion.height < 28) result.errors.push('titlebar too thin to grab');
      for (const key of Object.keys(result.dragRegion)) if (result.dragRegion[key] === 'drag') result.errors.push('CSS app-region came back: ' + key);
      /* Windows 上透明像素不参与命中测试：拖动面必须有不透明背景，否则点上去会穿透。 */
      result.dragSurface = await win.webContents.executeJavaScript(`(()=>{const cs=getComputedStyle(document.body);return {preview:document.body.classList.contains('preview'),painted:cs.backgroundImage!=='none'||cs.backgroundColor!=='rgba(0, 0, 0, 0)'}})()`);
      if (!result.dragSurface.painted) result.errors.push('drag surface is fully transparent: the window could not be grabbed');
      result.topmost = { alwaysOnTop: win.isAlwaysOnTop() };
      if (result.topmost.alwaysOnTop) result.errors.push('overlay stays on top of other windows');
      const windowBounds = win.getBounds();
      const onScreen = screen.getAllDisplays().some(d => overlaps(windowBounds, d.workArea));
      result.window = { bounds: windowBounds, onScreen };
      if (!onScreen) result.errors.push('window is off-screen');
      /* 震动强度条：演示模式下必须有明显量程，并在截屏前停在中高位便于核对样式。 */
      result.rumble = await win.webContents.executeJavaScript(`(async () => {
        const fill = document.getElementById('rumble-fill');
        if (!fill) return { present: false };
        let max = 0;
        for (let i = 0; i < 90; i++) {
          await new Promise(r => setTimeout(r, 40));
          max = Math.max(max, Number(fill.getAttribute('height')) || 0);
          if (max > 300) break;
        }
        for (let i = 0; i < 60; i++) {
          if ((Number(fill.getAttribute('height')) || 0) > 210) break;
          await new Promise(r => setTimeout(r, 40));
        }
        return { present: true, maxHeight: max, height: Number(fill.getAttribute('height')) || 0, y: fill.getAttribute('y') };
      })()`);
      if (!result.rumble.present || result.rumble.maxHeight < 150) result.errors.push('rumble gauge not driven by demo');
      /* 十字键按住必须和 ABXY 一样变红（`.dpad .surface` 曾经盖掉通用高亮）。 */
      result.dpadHighlight = await win.webContents.executeJavaScript(`(() => {
        const surface = id => document.querySelector('[data-button="' + id + '"] .surface');
        const present = [12, 13, 14, 15].every(id => !!surface(id));
        if (!present) return { present: false };
        const dpad = document.querySelector('[data-button="12"]');
        const rest = getComputedStyle(surface(12)).fill;
        dpad.classList.add('pressed');
        const pressed = getComputedStyle(surface(12)).fill;
        dpad.classList.remove('pressed');
        const abxy = document.querySelector('[data-button="0"]');
        abxy.classList.add('pressed');
        const face = getComputedStyle(surface(0)).fill;
        abxy.classList.remove('pressed');
        return { present: true, rest, pressed, face, same: pressed === face };
      })()`);
      if (!result.dpadHighlight.present) result.errors.push('dpad buttons missing from the controller svg');
      else if (!result.dpadHighlight.same) result.errors.push('dpad highlight differs from the face buttons: ' + JSON.stringify(result.dpadHighlight));
      /* 截图留档：必须走真实输入链路（readPads → 帧 → pressed 类）。手工加 class 没用，渲染循环下一帧就改回去了。 */
      const dpadRestore = { demo: inputConfig.demo, readPads };
      const pressButtons = ids => { inputConfig.demo = false; readPads = () => [{ index: 0, id: 'Native test controller', axes: [0, 0, 0, 0], buttons: Array.from({ length: 23 }, (_, i) => ({ value: ids.includes(i) ? 1 : 0 })) }]; };
      const litButtons = () => win.webContents.executeJavaScript(`[12, 13, 14, 15, 0].map(id => document.querySelector('[data-button="' + id + '"]').classList.contains('pressed'))`);
      pressButtons([0, 12, 13, 14, 15]);
      await new Promise(resolve => setTimeout(resolve, 400));
      result.dpadVisual = await litButtons();
      if (!result.dpadVisual.every(Boolean)) result.errors.push('dpad does not light up from real input: ' + JSON.stringify(result.dpadVisual));
      /* 只按「上」和 A 再截一张：未按的三个方向和中心正好是静止态，可以核对「+」形是否拼得完整。
         这张图是十字键造型与高亮的回归依据，改动 controller.svg 后必须重新核对。 */
      pressButtons([0, 12]);
      await new Promise(resolve => setTimeout(resolve, 400));
      fs.writeFileSync(path.join(artifactDir, 'dpad.png'), (await win.webContents.capturePage()).toPNG());
      inputConfig.demo = dpadRestore.demo;
      readPads = dpadRestore.readPads;

      /* 抖动效果：采样一段时间，刀身高度必须出现多个不同值。 */
      result.rumbleWobble = await win.webContents.executeJavaScript(`(async () => {
        const fill = document.getElementById('rumble-fill');
        const seen = new Set();
        for (let i = 0; i < 40; i++) { await new Promise(r => setTimeout(r, 25)); seen.add(fill.getAttribute('height')); }
        return { samples: seen.size };
      })()`);
      if (result.rumbleWobble.samples < 3) result.errors.push('rumble gauge does not move while rumbling');
      /* 展开震动捕获下拉框时，没选过目标程序应自动选中正在运行的忍龙 4。 */
      result.autoTarget = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        const game = [...select.options].find(option => /NINJAGAIDEN4/i.test(option.textContent));
        if (!game) return { hasGame: false, value: select.value };
        select.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
        await new Promise(r => setTimeout(r, 1500));
        return { hasGame: true, expected: game.value, value: select.value, label: select.selectedOptions[0]?.textContent || '', status: document.getElementById('rumble-status').textContent };
      })()`);
      if (result.autoTarget.hasGame && result.autoTarget.value !== result.autoTarget.expected) result.errors.push('rumble target not auto-selected when the dropdown opens');
      /* 清除按钮：必须解除注入，并把下拉框恢复成未选中。 */
      result.clearTarget = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        const before = select.value;
        document.getElementById('rumble-clear').click();
        await new Promise(r => setTimeout(r, 700));
        const info = await window.desktop.rumbleInfo();
        return { before, after: select.value, injectedPid: info.injectedPid, status: document.getElementById('rumble-status').textContent,
          remembered: localStorage.getItem('rumble-target') };
      })()`);
      if (result.clearTarget.before && result.clearTarget.after) result.errors.push('clear did not reset the dropdown');
      if (result.clearTarget.injectedPid) result.errors.push('clear did not detach the injected process');
      if (result.clearTarget.remembered) result.errors.push('clear did not forget the remembered target');

      /* 记忆里的进程已经不在了：重新打开覆层应回落到忍龙 4，而不是卡在空选择。 */
      await win.webContents.executeJavaScript(`localStorage.setItem('rumble-target', JSON.stringify({ pid: 999999, name: 'ghost.exe' }))`);
      win.webContents.reload();
      await new Promise(resolve => setTimeout(resolve, 2000));
      result.staleMemory = await win.webContents.executeJavaScript(`(async () => {
        const select = document.getElementById('rumble-process');
        const hasGame = [...select.options].some(o => /NINJAGAIDEN4/i.test(o.textContent));
        for (let i = 0; i < 50 && !select.value; i++) await new Promise(r => setTimeout(r, 100));
        const info = await window.desktop.rumbleInfo();
        return { hasGame, value: select.value, injectedPid: info.injectedPid, label: select.selectedOptions[0]?.textContent || '' };
      })()`);
      /* 游戏没在运行时没有可回落的目标，这条只在检测到游戏时才要求命中。 */
      if (result.staleMemory.hasGame && Number(result.staleMemory.value || 0) !== result.staleMemory.injectedPid) result.errors.push('stale memory blocked the fallback to the game');
      fs.mkdirSync(artifactDir, { recursive: true });
      fs.writeFileSync(path.join(artifactDir, 'preview.png'), (await win.webContents.capturePage()).toPNG());
      const source = new BrowserWindow({ width: 1000, height: 720, show: false, frame: false, transparent: true, webPreferences: { backgroundThrottling: false } });
      await source.loadURL(sourceUrl);
      inputConfig.demo = false;
      const sample = { buttons: Array(23).fill(0), left: [.75, -.5], right: [0, 0], connected: true, buttonCount: 23 };
      sample.buttons[0] = 1; sample.buttons[6] = .5;
      await new Promise(resolve => setTimeout(resolve, 200));
      inputConfig.demo = false;
      inputConfig.device = 'auto';
      readPads = () => [{ index: 0, id: 'Native test controller', axes: [.75, -.5, 0, 0], buttons: sample.buttons.map(value => ({ value })) }];
      win.minimize();
      await new Promise(resolve => setTimeout(resolve, 150));
      const broadcast = await source.webContents.executeJavaScript(`({transparent:getComputedStyle(document.body).backgroundColor,header:getComputedStyle(document.querySelector('header')).display,buttons:document.querySelectorAll('[data-button]').length,pressed:document.querySelector('[data-button="0"]').classList.contains('pressed'),trigger:document.querySelector('#lt-value').textContent})`);
      if (broadcast.transparent !== 'rgba(0, 0, 0, 0)' || broadcast.header !== 'none' || broadcast.buttons < 19 || !broadcast.pressed || broadcast.trigger !== '50%') result.errors.push('broadcast source failed');
      result.broadcast = broadcast;
      result.background = { focused: win.isFocused(), minimized: win.isMinimized(), backend: inputError || backendName };
      if (inputError || win.isFocused()) result.errors.push('native background input failed');
      /* 震动捕获：DLL 必须真的落在可被目标进程 LoadLibrary 的位置（打包版在 resources 根目录）。 */
      result.rumbleHook = { dll: rumbleDll, exists: fs.existsSync(rumbleDll), supported: !!rumbleSource, packaged: app.isPackaged };
      if (!result.rumbleHook.exists) result.errors.push('RumbleHook.dll not found at ' + rumbleDll);
      if (!result.rumbleHook.supported) result.errors.push('rumble-source unavailable: ' + rumbleError);
      await source.loadURL(sourceUrl + '?demo=1');
      await new Promise(resolve => setTimeout(resolve, 300));
      fs.writeFileSync(path.join(artifactDir, 'overlay.png'), (await source.webContents.capturePage()).toPNG());
      source.destroy();
      log('smoke result', safeJson(result.errors));
      fs.writeFileSync(path.join(artifactDir, 'smoke.json'), JSON.stringify(result, null, 2));
      app.exit(result.errors.length ? 1 : 0);
    } catch (error) { log('smoke failed', error?.stack || String(error)); console.error(error); app.exit(1); }
  }
}
