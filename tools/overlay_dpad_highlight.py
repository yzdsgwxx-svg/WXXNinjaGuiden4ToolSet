from pathlib import Path

root = Path(r'D:\APP\WXXNinjaGuiden4ToolSet')

# ---------- style.css：十字键按下与 ABXY 同样变红 ----------
p = root / 'overlay/style.css'
s = p.read_text(encoding='utf-8')
old = ".dpad .surface{fill:#25272b;stroke:#63615e}"
assert old in s, 'dpad surface rule not found'
new = (old + "\n"
       "/* 十字键按下要和 ABXY 一样变红：`.dpad .surface` 与 `.pressed .surface` 特异性相同、"
       "又写在后面，会把通用高亮盖掉，所以单独补一条更高特异性的规则。 */\n"
       ".dpad .pressed .surface{fill:#df344b;stroke:#ffd8ba;filter:url(#glow)}\n"
       ".dpad .pressed path:not(.surface){stroke:#fff3d4}")
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('style.css: dpad pressed highlight added')

# ---------- main.js：自检加一条十字键高亮断言 ----------
p = root / 'overlay/main.js'
s = p.read_text(encoding='utf-8')
anchor = "      /* 抖动效果：采样一段时间，刀身高度必须出现多个不同值。 */"
assert anchor in s, 'wobble anchor not found'
if 'dpadHighlight' not in s:
    check = """      /* 十字键按住必须和 ABXY 一样变红（`.dpad .surface` 曾经盖掉通用高亮）。 */
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

""" + anchor
    s = s.replace(anchor, check, 1)
    p.write_text(s, encoding='utf-8')
    print('main.js: dpad highlight assertion added')
else:
    print('main.js: assertion already present')
