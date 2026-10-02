from pathlib import Path
p = Path('overlay/main.js'); s = p.read_text(encoding='utf-8')

# 游戏没在运行时不该要求 fallback 命中
old = """        const select = document.getElementById('rumble-process');
        for (let i = 0; i < 50 && !select.value; i++) await new Promise(r => setTimeout(r, 100));
        const info = await window.desktop.rumbleInfo();
        return { value: select.value, injectedPid: info.injectedPid, label: select.selectedOptions[0]?.textContent || '' };
      })()`);
      if (!result.staleMemory.value || Number(result.staleMemory.value) !== result.staleMemory.injectedPid) result.errors.push('stale memory blocked the fallback to the game');"""
new = """        const select = document.getElementById('rumble-process');
        const hasGame = [...select.options].some(o => /NINJAGAIDEN4/i.test(o.textContent));
        for (let i = 0; i < 50 && !select.value; i++) await new Promise(r => setTimeout(r, 100));
        const info = await window.desktop.rumbleInfo();
        return { hasGame, value: select.value, injectedPid: info.injectedPid, label: select.selectedOptions[0]?.textContent || '' };
      })()`);
      /* 游戏没在运行时没有可回落的目标，这条只在检测到游戏时才要求命中。 */
      if (result.staleMemory.hasGame && Number(result.staleMemory.value || 0) !== result.staleMemory.injectedPid) result.errors.push('stale memory blocked the fallback to the game');"""
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('smoke: fallback check now requires a running game')
