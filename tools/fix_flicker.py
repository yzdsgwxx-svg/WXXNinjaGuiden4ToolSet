from pathlib import Path

p = Path('src/launcher.cpp')
s = p.read_text(encoding='utf-8')

# SetWindowTextW repaints a control even when the string is identical, so the 1 s status poll
# made every label and owner-draw button blink. Compare first, repaint only on real changes.
helper = '''/* ---------- 避免每秒重绘 ---------- */
/* SetWindowTextW 即使内容相同也会重绘控件；1 秒轮询直接调用会让整个面板每秒闪一次。
   先比较，只有真的变了才设置文本并重绘。 */
static void SetText(HWND control,const std::wstring& text){
    if(!control)return;
    wchar_t current[512]{};
    int n=GetWindowTextW(control,current,512);
    if(n>0&&size_t(n)==text.size()&&wcsncmp(current,text.c_str(),n)==0)return;
    SetWindowTextW(control,text.c_str());
    InvalidateRect(control,nullptr,FALSE);
}
'''
anchor = 'static void RefreshModState(){'
assert anchor in s
s = s.replace(anchor, helper + anchor, 1)

s = s.replace(
    '    SetWindowTextW(gModState,text.c_str());\n'
    '    if(gMain){SetWindowTextW(GetDlgItem(gMain,ID_MOD_LOAD),gWeaponOn?L"六槽武器：开启":L"六槽武器：关闭");InvalidateRect(GetDlgItem(gMain,ID_MOD_LOAD),nullptr,FALSE);}\n',
    '    SetText(gModState,text);\n'
    '    if(gMain)SetText(GetDlgItem(gMain,ID_MOD_LOAD),gWeaponOn?L"六槽武器：开启":L"六槽武器：关闭");\n')

# Save state label: same treatment so the 1 s path (and the empty-profile path) never flickers.
s = s.replace('    SetWindowTextW(gSaveState,text.c_str());',
              '    SetText(gSaveState,text);')

# Overlay row in the timer used to rewrite both texts and force a repaint every second.
s = s.replace(
    '        SetWindowTextW(gOverlayState,gOverlayPending?(gOverlayRequested?L"正在打开…":L"正在关闭…"):(gOverlayOn?L"运行中 · 手柄输入与震动捕获":L"未打开"));\n'
    '        SetWindowTextW(GetDlgItem(w,ID_OVERLAY_OPEN),gOverlayOn?L"控制器覆层：开启":L"控制器覆层：关闭");\n'
    '        InvalidateRect(GetDlgItem(w,ID_OVERLAY_OPEN),nullptr,FALSE);\n',
    '        SetText(gOverlayState,gOverlayPending?(gOverlayRequested?L"正在打开…":L"正在关闭…"):(gOverlayOn?L"运行中 · 手柄输入与震动捕获":L"未打开"));\n'
    '        SetText(GetDlgItem(w,ID_OVERLAY_OPEN),gOverlayOn?L"控制器覆层：开启":L"控制器覆层：关闭");\n')

assert 'InvalidateRect(GetDlgItem' not in s
assert s.count('static void SetText(') == 1
p.write_text(s, encoding='utf-8')
print('flicker fix applied')
