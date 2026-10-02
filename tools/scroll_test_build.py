"""滚动容器验证：生成改类名的临时面板副本（可与你正在用的面板同时运行）。

副本里额外塞一个占位控件把内容顶出视口，用来确认滚动条出现、且滚动时卡片绘制
和子控件一起移动（SW_SCROLLCHILDREN）。
"""
from pathlib import Path
import subprocess, sys

root = Path(r'D:\APP\WXXNinjaGuiden4ToolSet')
src = (root / 'src/launcher.cpp').read_text(encoding='utf-8')

# 换类名/标题，避免和正在运行的面板抢单实例
n = src.count('L"WXXNinjaGuiden4ToolSet"')
src = src.replace('L"WXXNinjaGuiden4ToolSet"', 'L"WXXToolsetScrollTest"')
print('renamed strings:', n)

anchor = 'Add(c,L"BUTTON",L"查看日志",0,654,506-kScrollTop,96,32,ID_OPENSAVES);'
assert anchor in src
src = src.replace(anchor, anchor + '\n        Add(c,L"BUTTON",L"滚动测试占位",0,48,620-kScrollTop,200,40,199);', 1)

# 临时日志：确认滚轮消息到底有没有进 ScrollProc、参数是多少
wheel = ('case WM_MOUSEWHEEL:{\n        SCROLLINFO si{};si.cbSize=sizeof si;si.fMask=SIF_POS;'
         'GetScrollInfo(w,SB_VERT,&si);')
assert wheel in src
src = src.replace(wheel, wheel + '\n        Log(L"WHEELTEST msg=%u wp=%p delta=%d pos=%d",msg,(void*)wp,GET_WHEEL_DELTA_WPARAM(wp),si.nPos);', 1)

# 容器入口日志：确认滚轮/滚动消息到底有没有进来
head = ('static LRESULT CALLBACK ScrollProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){\n    switch(msg){')
assert head in src
src = src.replace(head, ('static LRESULT CALLBACK ScrollProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){\n'
                         '    if(msg==0x020A||msg==0x0115||msg==0x0020)Log(L"SCROLLMSG msg=%u wp=%p",msg,(void*)wp);\n'
                         '    switch(msg){'), 1)

# ScrollContent 内部：请求值、夹取上限、结果
sc = ('static void ScrollContent(int pos){\n    if(!gScrollBox)return;')
assert sc in src
src = src.replace(sc, ('static void ScrollContent(int pos){\n'
                       '    Log(L"SCROLLFN enter req=%d box=%p",pos,(void*)gScrollBox);\n'
                       '    if(!gScrollBox)return;'), 1)
tail = '    ScrollWindowEx(gScrollBox,0,si.nPos-pos,nullptr,nullptr,nullptr,nullptr,SW_INVALIDATE|SW_ERASE|SW_SCROLLCHILDREN);\n    si.fMask=SIF_POS;si.nPos=pos;SetScrollInfo(gScrollBox,SB_VERT,&si,TRUE);'
assert tail in src
src = src.replace(tail, '    Log(L"SCROLLFN apply old=%d new=%d max=%d page=%u",si.nPos,pos,maxPos,unsigned(si.nPage));\n' + tail +
                  '\n    {SCROLLINFO chk{};chk.cbSize=sizeof chk;chk.fMask=SIF_POS;GetScrollInfo(gScrollBox,SB_VERT,&chk);'
                  'Log(L"SCROLLFN verify pos=%d",chk.nPos);}', 1)
clip = '    if(pos==si.nPos)return;'
assert clip in src
src = src.replace(clip, '    if(pos==si.nPos){Log(L"SCROLLFN noop pos=%d",pos);return;}', 1)

out = root / 'build/launcher_scrolltest.cpp'
out.write_text(src, encoding='utf-8')
print('wrote', out)
print('now compile it from PowerShell (python subprocess with piped stdio is blocked by the sandbox):')
print(r'  cmd /c "call \"...vcvars64.bat\" >nul && cd /d %s && cl /nologo /std:c++17 /utf-8 /O2 /MT /W4 /EHsc '
      r'launcher_scrolltest.cpp toolset.res user32.lib gdi32.lib /link /SUBSYSTEM:WINDOWS /OUT:%%TEMP%%\WXXScrollTest.exe"' % (root / 'build'))
