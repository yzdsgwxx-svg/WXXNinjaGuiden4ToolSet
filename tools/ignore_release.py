from pathlib import Path
p = Path('.gitignore'); s = p.read_text()
if '/release/' not in [l.strip() for l in s.splitlines()]:
    s = s.rstrip('\n') + '\n/release/\n'
    p.write_text(s)
    print('release/ ignored')
else:
    print('release/ already ignored')
