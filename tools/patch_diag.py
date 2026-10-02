from pathlib import Path
p=Path('tools/make_diag.py');s=p.read_text(encoding='utf-8')
old="src = src.replace(\"CreateWindowW(wc.lpszClassName"
add="src = src.replace('FindWindowW(L\"WXXNinjaGuiden4ToolSet\",nullptr)', 'FindWindowW(L\"WXXToolsetDiag\",nullptr)')\n"
if 'WXXToolsetDiag\\",nullptr' not in s:
    s=s.replace(old, add+old,1)
p.write_text(s,encoding='utf-8')
