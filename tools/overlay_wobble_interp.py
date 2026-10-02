from pathlib import Path

root = Path('overlay')

# ---------- input.js: sine interpolation, ±2.5% ----------
p = root / 'input.js'
s = p.read_text(encoding='utf-8')
old = """  /* 震动强度抖动：强度非零时把显示值在 ±amplitude 之间以 hz 次/秒来回切换，
     进度条就能直观看出「正在震动」。amplitude 用进度条比例表示（0.05 = 上下各 5%）。 */
  function wobble(value, timeMs, amplitude = .05, hz = 8, threshold = .02) {
    const base = clamp(value, 0, 1);
    if (base < threshold) return base;
    const phase = Math.floor(clamp(timeMs, 0, 1e12) / 1000 * hz * 2) % 2;
    return clamp(base + (phase ? amplitude : -amplitude), 0, 1);
  }"""
new = """  /* 震动强度抖动：强度非零时显示值在 ±amplitude 之间以 hz 次/秒摆动，
     进度条就能直观看出「正在震动」。用正弦插值，值是连续变化的，不是在上限/下限之间硬切。
     amplitude 用进度条比例表示（0.025 = 上下各 2.5%）。 */
  function wobble(value, timeMs, amplitude = .025, hz = 8, threshold = .02) {
    const base = clamp(value, 0, 1);
    if (base < threshold) return base;
    const phase = Math.sin(clamp(timeMs, 0, 1e12) / 1000 * hz * Math.PI * 2);
    return clamp(base + phase * amplitude, 0, 1);
  }"""
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# ---------- unit test ----------
p = root / 'tests/input.test.js'
s = p.read_text(encoding='utf-8')
start = s.index("test('rumble wobble")
s = s[:start].rstrip() + """
test('rumble wobble interpolates ±2.5% smoothly at 8 Hz',()=>{
 const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
 near(wobble(.5,0),.5);            // 从中位出发
 near(wobble(.5,31.25),.525);      // 1/4 周期到上限
 near(wobble(.5,93.75),.475);      // 3/4 周期到下限
 near(wobble(.5,125),.5);          // 一个周期回到中位
 let prev=wobble(.5,0), maxJump=0;
 for(let t=4;t<=250;t+=4){const v=wobble(.5,t);maxJump=Math.max(maxJump,Math.abs(v-prev));prev=v;}
 assert.ok(maxJump<.02,`值有跳变，说明没插值：${maxJump}`);   // 逐帧必须平滑
 near(wobble(0,0),0); near(wobble(.01,0),.01);               // 不震动 / 低于阈值不抖
 near(wobble(.99,31.25),1); near(wobble(.5,0,0),.5);         // 夹在 0..1；幅度 0 = 关闭
});
"""
p.write_text(s, encoding='utf-8')
print('wobble: ±2.5% with sine interpolation')
