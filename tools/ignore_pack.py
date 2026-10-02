from pathlib import Path
p=Path('.gitignore');s=p.read_text()
for line in ['/overlay/pack/','/overlay/dist/']:
    if line not in s: s+=line+'\n'
p.write_text(s)
