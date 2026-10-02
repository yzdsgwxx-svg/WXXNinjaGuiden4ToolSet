from pathlib import Path
import re,json
p=Path('overlay')
h=(p/'index.html').read_text(encoding='utf-8')
a=h.index('<aside');b=h.index('</aside>',a)+len('</aside>')
h=h[:a]+'''<aside id="settings">
  <div class="rumble-row"><label for="rumble-process" class="rumble-title">震动捕获</label>
    <select id="rumble-process"><option value="">选择目标程序</option></select>
    <output id="rumble-value">0%</output><button id="copy-url">复制直播 URL</button>
  </div>
  <p id="rumble-status" role="status">选择程序后自动连接</p>
  <input id="source-url" type="hidden">
</aside>'''+h[b:]
h=h.replace('VADER 5 PRO / v1.0.3','CONTROLLER / v1.1.0').replace('按住标题栏任意位置拖动窗口','').replace('忍龙 4 · 黑武士 5 Pro','WXX · 控制器覆层')
(p/'index.html').write_text(h,encoding='utf-8')
s=(p/'renderer.js').read_text(encoding='utf-8')
s=s.replace("demo:$('demo')?.checked","demo:false")
s=s.replace("  config.mapping =", "  config = {...config,deadzone:8,scale:100,opacity:100,extras:true,backdrop:true,device:'auto'};\n  config.mapping =",1)
a=s.index('  async function refreshRumbleProcesses()');b=s.index('  if (!source) window.desktop',a)
s=s[:a]+'''  let refreshing = null, injecting = false;
  async function refreshRumbleProcesses() {
    if (!window.desktop?.rumbleProcesses || !rumbleProcess) return;
    if (refreshing) return refreshing;
    const selected = rumbleProcess.value;
    refreshing = (async () => {
      try {
        const list = await window.desktop.rumbleProcesses();
        rumbleProcess.replaceChildren(new Option('选择目标程序', ''));
        for (const item of list) rumbleProcess.append(new Option(`${item.name} (${item.pid})`, String(item.pid)));
        if (list.some(item => String(item.pid) === selected)) rumbleProcess.value = selected;
      } catch (error) { rumbleStatusLabel.textContent = '刷新失败：' + error.message; }
    })();
    try { await refreshing; } finally { refreshing = null; }
  }
  // Refresh before opening the native popup, including the keyboard path.
  let reopening = false;
  async function openProcesses(event) {
    if (reopening || injecting) return;
    event.preventDefault();
    await refreshRumbleProcesses();
    reopening = true;
    rumbleProcess.focus();
    try { rumbleProcess.showPicker(); } catch { /* Older Chromium: refreshed list is ready for the next click. */ }
    reopening = false;
  }
  rumbleProcess?.addEventListener('pointerdown', openProcesses);
  rumbleProcess?.addEventListener('keydown', event => {
    if ([' ', 'Enter', 'ArrowDown', 'F4'].includes(event.key)) openProcesses(event);
  });
  rumbleProcess?.addEventListener('change', async () => {
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
'''+s[b:]
s=s.replace('const RUMBLE_TOP = 24, RUMBLE_BOTTOM = 466;', 'const RUMBLE_TOP = 24, RUMBLE_BOTTOM = 464;')
(p/'renderer.js').write_text(s,encoding='utf-8')
svg=(p/'controller.svg').read_text(encoding='utf-8')
a=svg.index('<g id="rumble-gauge">')
# Original layered PNGs: base blade starts around y=14..800; energy must be scaled into its blade cutout.
svg=svg[:a]+'''<g id="rumble-gauge">
 <defs><clipPath id="energy-reveal"><rect id="rumble-fill" x="860" y="464" width="90" height="0"/></clipPath></defs>
 <image href="sword-base.png" x="549" y="15" width="690" height="690"/>
 <g clip-path="url(#energy-reveal)"><image href="sword-energy.png" x="549" y="15" width="690" height="499" preserveAspectRatio="none"/></g>
</g>
</svg>'''
(p/'controller.svg').write_text(svg,encoding='utf-8')
s=(p/'server.js').read_text(encoding='utf-8').replace("'/controller.svg': 'controller.svg'", "'/controller.svg': 'controller.svg', '/sword-base.png':'sword-base.png', '/sword-energy.png':'sword-energy.png'").replace("'.svg': 'image/svg+xml'", "'.svg': 'image/svg+xml', '.png':'image/png'")
(p/'server.js').write_text(s,encoding='utf-8')
s=(p/'style.css').read_text(encoding='utf-8')+'''
/* Transparent pixels around the old rounded header were not hit-testable on Windows. */
header{height:48px;border-radius:6px;background:#19191f;-webkit-app-region:drag;isolation:isolate}
header :not(nav):not(button){-webkit-app-region:drag;pointer-events:none}
header nav,header nav *{-webkit-app-region:no-drag;pointer-events:auto}
body{padding:12px}aside{padding:12px 16px}.rumble-row{margin:0;gap:14px}.rumble-title{font-size:12px}
#rumble-status{min-height:16px;margin-top:8px}button,select{font-size:12px;padding:8px 12px;border-radius:6px}
'''
(p/'style.css').write_text(s,encoding='utf-8')
pkg=json.loads((p/'package.json').read_text());pkg['version']='1.1.0';pkg['name']='wxx-ng4-controller-overlay';(p/'package.json').write_text(json.dumps(pkg,indent=2)+'\n')
s=(p/'main.js').read_text(encoding='utf-8')
s=s.replace("...bounds, minWidth:","icon: path.join(__dirname, 'overlay.ico'), ...bounds, minWidth:")
s=re.sub(r"const icon = nativeImage.createFromDataURL\([^\n]+", "const icon = nativeImage.createFromPath(path.join(__dirname, 'overlay.ico'));",s)
s=s.replace("document.querySelector('#demo').click();", "")
s=s.replace("      const result = await win.webContents", "      inputConfig.demo = true;\n      const result = await win.webContents",1)
s=s.replace("await win.webContents.executeJavaScript(`document.querySelector('#demo').checked=false;`);", "inputConfig.demo = false;")
s=s.replace("app.on('second-instance',", "app.on('second-instance',")
(p/'main.js').write_text(s,encoding='utf-8')
