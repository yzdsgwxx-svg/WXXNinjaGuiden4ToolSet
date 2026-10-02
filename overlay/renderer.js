/* All artwork is local SVG; the broadcast page never needs controller access. */
window.addEventListener('error', event => window.desktop?.log?.(`renderer error: ${event.message} @${event.filename}:${event.lineno}`));
window.addEventListener('unhandledrejection', event => window.desktop?.log?.(`renderer rejection: ${event.reason?.message || event.reason}`));
(async function () {
  const $ = id => document.getElementById(id);
  const source = location.pathname === '/overlay';
  let config = {deadzone:8,scale:100,opacity:100,extras:true,backdrop:true,device:'auto',mapping:{C:17,Z:18}};
  try { const saved = JSON.parse(localStorage.getItem('ninja-overlay') || '{}'); config = {...config,...saved,mapping:{...config.mapping,...saved.mapping}}; } catch {}
  config = {...config,deadzone:8,scale:100,opacity:100,extras:true,backdrop:true,device:'auto'};
  config.mapping = {C:config.mapping.C,Z:config.mapping.Z};
  /* 手柄图失败也不能拖垮整个界面：标题栏和按钮必须一直可用。 */
  try { $('controller').innerHTML = await (await fetch('controller.svg')).text(); }
  catch (error) { window.desktop?.log?.(`controller.svg 加载失败：${error.message}`); }
  document.body.classList.toggle('source', source);
  const nodes = [...document.querySelectorAll('[data-button]')];
  let remote = null, signature = '', remoteTime = 0;
  function applySettings() {
    for(const key of ['deadzone','scale','opacity']) { const input=$(key), output=$(key+'-value'); if(input) input.value=config[key]; if(output) output.textContent=config[key]+'%'; }
    for(const key of ['extras','backdrop']) { const input=$(key); if(input) input.checked=config[key]; }
    document.body.classList.toggle('preview', !source && config.backdrop);
    document.body.classList.toggle('hidden-extras', !config.extras);
    const controller=$('controller');
    controller.style.transform = `scale(${source ? 1 : config.scale/100})`;
    controller.style.opacity = config.opacity/100;
    document.querySelectorAll('[data-extra]').forEach(n => n.dataset.button = config.mapping[n.dataset.extra]);
  }
  applySettings();
  function sendConfig(){window.desktop?.configure({...config,demo:false});}
  sendConfig();
  const demo=$('demo'); if(demo) demo.onchange=sendConfig;
  for(const key of ['deadzone','scale','opacity','extras','backdrop']) $(key)?.addEventListener('input', () => {
    config[key] = $(key).type === 'checkbox' ? $(key).checked : Number($(key).value);
    applySettings(); localStorage.setItem('ninja-overlay',JSON.stringify(config));sendConfig();
  });
  for(const [key,value] of Object.entries(config.mapping)) {
    const label = document.createElement('label'); label.textContent = key;
    const select = document.createElement('select');
    for(let i=-1;i<32;i++){const option=document.createElement('option');option.value=i;option.textContent=i<0?'禁用':`B${i}`;select.append(option);}
    select.value=value;label.append(select);$('mapping')?.append(label);
    select.onchange=()=>{config.mapping[key]=Number(select.value);applySettings();localStorage.setItem('ninja-overlay',JSON.stringify(config));sendConfig();};
  }
  const devices=$('devices'); if(devices) devices.onchange=()=>{config.device=devices.value;localStorage.setItem('ninja-overlay',JSON.stringify(config));sendConfig();};
  for(const name of ['minimize','close']) $(name).onclick=()=>window.desktop?.action(name);
  if(window.desktop) $('source-url').value=await window.desktop.sourceUrl();
  /* 震动捕获面板：列出进程 → 注入 RumbleHook.dll → 数值由 draw() 实时刷新。 */
  const rumbleProcess = $('rumble-process'), rumbleStatusLabel = $('rumble-status');
  let refreshing = null, injecting = false;
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
    /* 还没选中过目标程序时，展开就等于“自动找忍龙 4”；连上了就不用再弹列表。 */
    if (!rumbleProcess.value && await autoSelectGame()) return;
    reopening = true;
    rumbleProcess.focus();
    try { rumbleProcess.showPicker(); } catch { /* Older Chromium: refreshed list is ready for the next click. */ }
    reopening = false;
  }
  rumbleProcess?.addEventListener('pointerdown', openProcesses);
  rumbleProcess?.addEventListener('keydown', event => {
    if ([' ', 'Enter', 'ArrowDown', 'F4'].includes(event.key)) openProcesses(event);
  });
  /* 记住上次连上的目标：下次打开覆层优先恢复它，而不是每次都跳回忍龙 4。 */
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
    if (!pid || injecting) return false;
    injecting = true; rumbleProcess.disabled = true;
    rumbleStatusLabel.textContent = '正在连接…';
    let ok = false;
    try {
      const result = await window.desktop.rumbleInject(pid);
      ok = !!result.ok;
      if (ok) rememberTarget(pid, label); else forgetTarget();
      rumbleStatusLabel.textContent = ok ? `已连接 · ${label}` : `连接失败：${result.error || '未知错误'}`;
    } catch (error) { rumbleStatusLabel.textContent = '连接失败：' + error.message; }
    finally { injecting = false; rumbleProcess.disabled = false; }
    return ok;
  }
  /* 清除：停掉震动捕获，并把下拉框恢复成「未选中」。 */
  $('rumble-clear')?.addEventListener('click', async () => {
    if (injecting) return;
    try { await window.desktop?.rumbleClear?.(); }
    catch (error) { window.desktop?.log?.('rumble clear failed: ' + (error?.message || error)); }
    forgetTarget();
    if (rumbleProcess) rumbleProcess.value = '';
    if (rumbleStatusLabel) rumbleStatusLabel.textContent = '已清除 · 展开下拉框可重新选择';
  });
  rumbleProcess?.addEventListener('change', async () => {
    const pid = Number(rumbleProcess.value);
    if (!pid) return;
    await connectTarget(pid, rumbleProcess.selectedOptions[0]?.textContent || String(pid));
  });
  /* 目标程序还没选过时，找忍龙 4：在运行就直接选中并连上，省一次手动点击。
     覆层打开时跑一次，之后每次展开下拉框也跑。 */
  async function autoSelectGame() {
    if (!window.desktop?.rumbleInject || !rumbleProcess) return false;
    const game = [...rumbleProcess.options].find(option => /NINJAGAIDEN4/i.test(option.textContent));
    if (!game) return false;
    rumbleProcess.value = game.value;
    return await connectTarget(Number(game.value), game.textContent);
  }
  /* 打开覆层时的顺序：先恢复上次记住的目标（它还在运行才行），没有才去找忍龙 4。 */
  if (!source) refreshRumbleProcesses().then(async () => {
    if (rumbleProcess?.value) return;
    if (await restoreTarget()) return;
    if (!rumbleProcess?.value) autoSelectGame();
  });
  if (!source) window.desktop?.rumbleInfo?.().then(info => {
    if (rumbleStatusLabel && info && !info.supported) rumbleStatusLabel.textContent = '震动捕获不可用：' + (info.message || 'koffi 未加载');
  }).catch(() => {});
  /* 窗口拖动：按在非控件区域就开始移动窗口（控件保持正常点击）。 */
  const CONTROL = 'button,select,input,textarea,option,label,a';
  document.addEventListener('pointerdown', event => {
    if (event.button !== 0 || source) return;
    const target = event.target instanceof Element ? event.target : null;
    if (target && target.closest(CONTROL)) return;
    window.desktop?.startDrag?.();
  });
  /* 挂在 window 上：document 上的 pointerup 会冒泡上来，鼠标在窗口内任何位置松开都能结束拖动。 */
  window.addEventListener('pointerup', () => window.desktop?.endDrag?.());
  window.addEventListener('blur', () => window.desktop?.endDrag?.());

  $('copy-url').onclick=async()=>{
    try { if(window.desktop) window.desktop.copyUrl();else await navigator.clipboard.writeText($('source-url').value); $('copy-url').textContent='已复制';setTimeout(()=>$('copy-url').textContent='复制 URL',1600); } catch { $('source-url').select(); }
  };
  {
    const stream=new EventSource('/events');
    stream.onmessage=event=>{try{remote=JSON.parse(event.data);remoteTime=performance.now();frame(remoteTime);}catch(error){window.desktop?.log?.(`SSE 解析失败：${error.message}`);}};
    stream.onerror=()=>{remote=null;};
  }
  /* 太刀形震动强度表：能量从柄(466) 向切先(20) 增长，做一点平滑避免跳变。 */
  const RUMBLE_TOP = 24, RUMBLE_BOTTOM = 464;
  let rumbleLevel = 0;
  function setRumble(value) {
    const target = Math.max(0, Math.min(1, Number(value) || 0));
    rumbleLevel += (target - rumbleLevel) * 0.3;
    const fill = $('rumble-fill');
    if (!fill) return;
    /* 有震动时显示值在 ±5% 之间以 8 次/秒抖动，静止时如实显示。 */
    const shown = Input.wobble(rumbleLevel, performance.now());
    const height = Math.round((RUMBLE_BOTTOM - RUMBLE_TOP) * shown);
    fill.setAttribute('y', String(RUMBLE_BOTTOM - height));
    fill.setAttribute('height', String(height));
    const label = $('rumble-value');
    if (label) label.textContent = Math.round(shown * 100) + '%';
  }
  function draw(state) {
    if(state.config && source){config={...config,...state.config};applySettings();}
    const buttons=state.buttons||[];
    nodes.forEach(node=>{
      const index=Number(node.dataset.button);
      node.classList.toggle('pressed',(buttons[index]||0)>.12);
      if(node.dataset.extra) node.classList.toggle('unavailable',index<0 || index>=(state.buttonCount||0));
    });
    const left=state.left||[0,0], right=state.right||[0,0];
    $('left-stick')?.setAttribute('transform',`translate(${left[0]*19} ${left[1]*19})`);
    $('right-stick')?.setAttribute('transform',`translate(${right[0]*19} ${right[1]*19})`);
    for(const [prefix,index,start] of [['lt',6,242],['rt',7,674]]){
      const v=buttons[index]||0;
      const fill=$(prefix+'-fill'), value=$(prefix+'-value');
      if(fill) fill.setAttribute('d',`M${start} 111H${start+84}V${111-v*72}H${start}Z`);
      if(value) value.textContent=Math.round(v*100)+'%';
    }
    document.body.classList.toggle('connected',!!state.connected);
    const device=$('device'); if(device) device.textContent=state.name || '连接手柄后按任意键 · 推荐 XInput 模式';
    const mode=$('mode-label'); if(mode) mode.textContent=state.demo?'DEMO / 演示':state.connected?'LIVE INPUT':'WAITING';
    setRumble(state.rumble);
  }
  function frame(now){
    let state=remote && now-remoteTime<1500?remote:Input.normalize(null);
    if(source && new URLSearchParams(location.search).get('demo')==='1') state={...Input.demo(now/1000),buttonCount:19,demo:true};
    if(!source){
      const pads=state.devices||[];
      const newSignature=pads.map(p=>p.index+':'+p.id).join('|');
      if(newSignature!==signature){
        signature=newSignature;const list=$('devices');
        if(list){list.replaceChildren(new Option('自动选择','auto'));pads.forEach(p=>list.append(new Option(p.id,String(p.index))));list.value=config.device;}
      }
    }
    draw(state);
  }
  // Rendering is independent of native input polling in the main process.
  setInterval(()=>{try{frame(performance.now());}catch(error){window.desktop?.log?.(`渲染失败：${error.message}`);}},16);
  frame(performance.now());
})();
