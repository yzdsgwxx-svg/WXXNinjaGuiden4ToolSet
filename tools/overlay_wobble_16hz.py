from pathlib import Path

root = Path('overlay')

# ---------- 频率翻倍：8 Hz -> 16 Hz ----------
p = root / 'input.js'
s = p.read_text(encoding='utf-8')
old = "  function wobble(value, timeMs, amplitude = .025, hz = 8, threshold = .02) {"
new = "  function wobble(value, timeMs, amplitude = .025, hz = 16, threshold = .02) {"
assert old in s
s = s.replace(old, new, 1)
s = s.replace("强度非零时显示值在 ±amplitude 之间以 hz 次/秒摆动",
              "强度非零时显示值在 ±amplitude 之间以 hz 次/秒摆动（当前 16 次/秒）", 1)
p.write_text(s, encoding='utf-8')

# ---------- 单测跟着改成 62.5ms 一个周期 ----------
p = root / 'tests/input.test.js'
s = p.read_text(encoding='utf-8')
start = s.index("test('rumble wobble")
s = s[:start].rstrip() + """
test('rumble wobble interpolates ±2.5% smoothly at 16 Hz',()=>{
 const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
 near(wobble(.5,0),.5);            // 从中位出发
 near(wobble(.5,15.625),.525);     // 1/4 周期到上限
 near(wobble(.5,46.875),.475);     // 3/4 周期到下限
 near(wobble(.5,62.5),.5);         // 一个周期回到中位
 let prev=wobble(.5,0), maxJump=0;
 for(let t=2;t<=250;t+=2){const v=wobble(.5,t);maxJump=Math.max(maxJump,Math.abs(v-prev));prev=v;}
 assert.ok(maxJump<.025,`值有跳变，说明没插值：${maxJump}`);   // 逐帧必须平滑（方波会是 0.05）
 near(wobble(0,0),0); near(wobble(.01,0),.01);               // 不震动 / 低于阈值不抖
 near(wobble(.99,15.625),1); near(wobble(.5,0,0),.5);        // 夹在 0..1；幅度 0 = 关闭
});
"""
p.write_text(s, encoding='utf-8')
print('wobble: 16 Hz (double speed)')
