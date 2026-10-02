from pathlib import Path
s=Path('build/diag_toolset.cpp').read_text(encoding='utf-8')
s=s.replace('if(n>0&&size_t(n)==text.size()&&wcsncmp(current,text.c_str(),n)==0)return;','if(false)return; /* 对照：模拟修复前每秒无条件重设文本 */')
s=s.replace('WXXToolset_diag.txt','WXXToolset_diag_before.txt')
Path('build/diag_before.cpp').write_text(s,encoding='utf-8')
print('before-behaviour source written')
