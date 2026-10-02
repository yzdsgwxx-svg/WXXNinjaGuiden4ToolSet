(function (root) {
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, Number.isFinite(v) ? v : 0));
  function stick(x, y, deadzone) {
    x = clamp(x, -1, 1); y = clamp(y, -1, 1);
    const length = Math.hypot(x, y), dz = clamp(deadzone, 0, .5);
    if (length <= dz) return [0, 0];
    const magnitude = Math.min(1, (length - dz) / (1 - dz));
    return [x / length * magnitude, y / length * magnitude];
  }
  function normalize(pad, deadzone = .08) {
    const buttons = Array.from({ length: Math.max(23, pad?.buttons?.length || 0) }, (_, i) => clamp(pad?.buttons?.[i]?.value, 0, 1));
    /* rumble 是手柄输出量，Windows 没有读回接口；真实模式先固定 0，等确定了数据源再填。 */
    return { buttons, left: stick(pad?.axes?.[0], pad?.axes?.[1], deadzone), right: stick(pad?.axes?.[2], pad?.axes?.[3], deadzone), rumble: 0 };
  }
  function demo(t) {
    const buttons = Array(23).fill(0);
    buttons[Math.floor(t * 2) % 17] = 1;
    buttons[6] = (Math.sin(t * 1.6) + 1) / 2;
    buttons[7] = (Math.cos(t * 1.6) + 1) / 2;
    /* 演示模式顺带驱动震动强度条，周期约 1.5 秒，便于快速看到满量程。 */
    return { buttons, left: [Math.sin(t) * .65, Math.cos(t) * .65], right: [Math.cos(t * .7) * .5, Math.sin(t * .7) * .5], rumble: (Math.sin(t * 4.2) + 1) / 2 };
  }
  /* 震动强度抖动：强度非零时显示值在 ±amplitude 之间以 hz 次/秒摆动（当前 16 次/秒），
     进度条就能直观看出「正在震动」。用正弦插值，值是连续变化的，不是在上限/下限之间硬切。
     amplitude 用进度条比例表示（0.025 = 上下各 2.5%）。 */
  function wobble(value, timeMs, amplitude = .025, hz = 16, threshold = .02) {
    const base = clamp(value, 0, 1);
    if (base < threshold) return base;
    const phase = Math.sin(clamp(timeMs, 0, 1e12) / 1000 * hz * Math.PI * 2);
    return clamp(base + phase * amplitude, 0, 1);
  }
  const api = { stick, normalize, demo, wobble };
  if (typeof module !== 'undefined') module.exports = api;
  else root.Input = api;
})(globalThis);
