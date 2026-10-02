from pathlib import Path

root = Path('overlay')

# ---------- input.js: pure wobble helper (unit-testable) ----------
p = root / 'input.js'
s = p.read_text(encoding='utf-8')
old = "  const api = { stick, normalize, demo };"
assert old in s
new = """  /* 震动强度抖动：强度非零时把显示值在 ±amplitude 之间以 hz 次/秒来回切换，
     进度条就能直观看出「正在震动」。amplitude 用进度条比例表示（0.05 = 上下各 5%）。 */
  function wobble(value, timeMs, amplitude = .05, hz = 8, threshold = .02) {
    const base = clamp(value, 0, 1);
    if (base < threshold) return base;
    const phase = Math.floor(clamp(timeMs, 0, 1e12) / 1000 * hz * 2) % 2;
    return clamp(base + (phase ? amplitude : -amplitude), 0, 1);
  }
  const api = { stick, normalize, demo, wobble };"""
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# ---------- renderer.js: drive the gauge through it ----------
p = root / 'renderer.js'
s = p.read_text(encoding='utf-8')
old = """    const fill = $('rumble-fill');
    if (!fill) return;
    const height = Math.round((RUMBLE_BOTTOM - RUMBLE_TOP) * rumbleLevel);
    fill.setAttribute('y', String(RUMBLE_BOTTOM - height));
    fill.setAttribute('height', String(height));
    const label = $('rumble-value');
    if (label) label.textContent = Math.round(target * 100) + '%';"""
assert old in s
new = """    const fill = $('rumble-fill');
    if (!fill) return;
    /* 有震动时显示值在 ±5% 之间以 8 次/秒抖动，静止时如实显示。 */
    const shown = Input.wobble(rumbleLevel, performance.now());
    const height = Math.round((RUMBLE_BOTTOM - RUMBLE_TOP) * shown);
    fill.setAttribute('y', String(RUMBLE_BOTTOM - height));
    fill.setAttribute('height', String(height));
    const label = $('rumble-value');
    if (label) label.textContent = Math.round(shown * 100) + '%';"""
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# ---------- unit test ----------
p = root / 'tests/input.test.js'
s = p.read_text(encoding='utf-8')
s = s.replace("const {normalize,stick}=require('../input');",
              "const {normalize,stick,wobble}=require('../input');", 1)
assert s.rstrip().endswith('});')
s = s.rstrip() + """
test('rumble wobble swings ±5% at 8 Hz, and stays truthful when idle',()=>{
 const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
 near(wobble(.5,0),.45); near(wobble(.5,62.5),.55); near(wobble(.5,125),.45);   // 8 Hz = 125ms 一个来回
 near(wobble(0,0),0); near(wobble(.01,0),.01);                                  // 不震动 / 低于阈值不抖
 near(wobble(.98,0),1); near(wobble(.02,0),0);                                  // 夹在 0..1
 near(wobble(1,0,0),1);                                                         // 幅度 0 = 关闭抖动
});
"""
p.write_text(s, encoding='utf-8')

# ---------- smoke: record that the gauge actually moves ----------
p = root / 'main.js'
s = p.read_text(encoding='utf-8')
anchor = "      /* 展开震动捕获下拉框时，没选过目标程序应自动选中正在运行的忍龙 4。 */"
assert anchor in s
probe = """      /* 抖动效果：采样一段时间，刀身高度必须出现多个不同值。 */
      result.rumbleWobble = await win.webContents.executeJavaScript(`(async () => {
        const fill = document.getElementById('rumble-fill');
        const seen = new Set();
        for (let i = 0; i < 40; i++) { await new Promise(r => setTimeout(r, 25)); seen.add(fill.getAttribute('height')); }
        return { samples: seen.size };
      })()`);
      if (result.rumbleWobble.samples < 3) result.errors.push('rumble gauge does not move while rumbling');
"""
s = s.replace(anchor, probe + anchor, 1)
p.write_text(s, encoding='utf-8')
print('overlay: rumble wobble (±5%, 8 Hz) added')
