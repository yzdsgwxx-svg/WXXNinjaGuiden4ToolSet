from pathlib import Path
p=Path('.gitignore');s=p.read_text()
add=['/overlay/build-pack/','/overlay/vendor/','/dist/ControllerOverlay/','/release/','/artifacts/']
lines=[l.strip() for l in s.splitlines()]
for a in add:
    if a not in lines: s = s.rstrip('\n') + '\n' + a + '\n'
p.write_text(s)
print(s)
