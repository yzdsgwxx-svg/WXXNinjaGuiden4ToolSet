from pathlib import Path

p = Path('overlay/main.js')
s = p.read_text(encoding='utf-8')

old = """    setTimeout(() => { writeProbe(); setInterval(writeProbe, 1500); }, 2500);
    setTimeout(() => { log('probe finished'); app.quit(); }, 45000);"""
new = """    /* 跨屏 DPI 自检：先在当前屏采样，再把窗口搬到另一块屏采样，最后对比视口/缩放。 */
    setTimeout(async () => {
      await writeProbe('probe.json');
      const other = screen.getAllDisplays().find(display => display.id !== screen.getPrimaryDisplay().id);
      if (other) {
        const before = win.getBounds();
        win.setBounds({ x: other.workArea.x + 60, y: other.workArea.y + 60, width: before.width, height: before.height });
        await new Promise(resolve => setTimeout(resolve, 1500));
        await writeProbe('probe-other-screen.json');
        win.setBounds(before);
        await new Promise(resolve => setTimeout(resolve, 800));
        await writeProbe('probe-back.json');
      }
      log('probe finished');
      app.quit();
    }, 2500);"""
assert old in s
s = s.replace(old, new, 1)

s = s.replace("    const writeProbe = async () => {\n      try {",
              "    const writeProbe = async (name) => {\n      try {", 1)
s = s.replace("        fs.writeFileSync(path.join(artifactDir, 'probe.json'), JSON.stringify({",
              "        fs.writeFileSync(path.join(artifactDir, name), JSON.stringify({", 1)
s = s.replace("          mediaNarrow: window.matchMedia('(max-width:620px)').matches,",
              "          mediaNarrow: window.matchMedia('(max-width:480px)').matches,", 1)
s = s.replace("""        log('probe written', safeJson({ bounds, innerWidth: metrics.innerWidth, dpr: metrics.dpr, scaleFactor: host.scaleFactor }));""",
              """        log('probe written', safeJson({ name, bounds, innerWidth: metrics.innerWidth, dpr: metrics.dpr, scaleFactor: host.scaleFactor }));""", 1)
p.write_text(s, encoding='utf-8')
print('probe: two-screen comparison added')
