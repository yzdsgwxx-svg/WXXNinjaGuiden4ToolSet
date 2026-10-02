from pathlib import Path

p = Path('overlay/main.js')
s = p.read_text(encoding='utf-8')

# The synthetic-drag probe cannot move a window (Electron only drags on real OS hits), drop it.
old_probe = """      /* 合成一次拖动（不动真实鼠标）：窗口跟着移动就说明 main 区确实能拖。 */
      const dragBefore = win.getBounds();
      const grab = await win.webContents.executeJavaScript(`(()=>{const r=document.querySelector('main').getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()`);
      win.webContents.sendInputEvent({ type: 'mouseDown', button: 'left', clickCount: 1, x: grab.x, y: grab.y });
      win.webContents.sendInputEvent({ type: 'mouseMove', button: 'left', x: grab.x + 70, y: grab.y + 50 });
      win.webContents.sendInputEvent({ type: 'mouseUp', button: 'left', x: grab.x + 70, y: grab.y + 50 });
      await new Promise(resolve => setTimeout(resolve, 400));
      const dragAfter = win.getBounds();
      result.dragMain = { before: dragBefore, after: dragAfter, moved: dragBefore.x !== dragAfter.x || dragBefore.y !== dragAfter.y };
      win.setBounds(dragBefore);
      await new Promise(resolve => setTimeout(resolve, 200));
"""
assert old_probe in s
new_probe = """      /* Windows 上透明像素不参与命中测试：拖动面必须有不透明背景，否则点上去会穿透。 */
      result.dragSurface = await win.webContents.executeJavaScript(`(()=>{const cs=getComputedStyle(document.body);return {preview:document.body.classList.contains('preview'),painted:cs.backgroundImage!=='none'||cs.backgroundColor!=='rgba(0, 0, 0, 0)'}})()`);
      if (!result.dragSurface.painted) result.errors.push('drag surface is fully transparent: the window could not be grabbed');
"""
s = s.replace(old_probe, new_probe, 1)
p.write_text(s, encoding='utf-8')
print('smoke: drag surface check replaces the synthetic-drag probe')
