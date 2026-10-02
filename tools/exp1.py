from pathlib import Path
p=Path('overlay/style.css');s=p.read_text(encoding='utf-8')
Path('overlay/style.css.bak').write_text(s,encoding='utf-8')
s=s.replace("body{display:flex;flex-direction:column;padding:16px;user-select:none;-webkit-app-region:drag}",
            "body{display:flex;flex-direction:column;padding:16px;user-select:none}")
p.write_text(s,encoding='utf-8')
print('experiment: body drag removed')
