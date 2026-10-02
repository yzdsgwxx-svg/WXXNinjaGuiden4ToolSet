from pathlib import Path
import re

src = Path('src/launcher.cpp').read_text(encoding='utf-8')

# Instrumented copy used only to count repaints; the shipped launcher is untouched.
src = src.replace('static HWND gLog,gProfileBox,gModState,gSaveState;',
                  'static HWND gLog,gProfileBox,gModState,gSaveState;\nstatic int gDiagTimer=0,gDiagSetText=0,gDiagDraw=0,gDiagPaint=0;')
src = src.replace('static void SetText(HWND control,const std::wstring& text){',
                  'static void SetText(HWND control,const std::wstring& text){\n    /* diag */')
src = src.replace('    SetWindowTextW(control,text.c_str());\n    InvalidateRect(control,nullptr,FALSE);',
                  '    ++gDiagSetText;\n    SetWindowTextW(control,text.c_str());\n    InvalidateRect(control,nullptr,FALSE);')
src = src.replace('    case WM_PAINT:{\n        PAINTSTRUCT ps;',
                  '    case WM_PAINT:{\n        ++gDiagPaint;\n        PAINTSTRUCT ps;')
src = src.replace('        auto d=reinterpret_cast<DRAWITEMSTRUCT*>(lp);if(d->CtlType!=ODT_BUTTON)break;',
                  '        auto d=reinterpret_cast<DRAWITEMSTRUCT*>(lp);if(d->CtlType!=ODT_BUTTON)break;++gDiagDraw;')
# Off-screen window so the diag run never disturbs the user, and stop after 8 timer ticks.
src = src.replace("wc.lpszClassName=L\"WXXNinjaGuiden4ToolSet\"", "wc.lpszClassName=L\"WXXToolsetDiag\"")
src = src.replace('FindWindowW(L"WXXNinjaGuiden4ToolSet",nullptr)', 'FindWindowW(L"WXXToolsetDiag",nullptr)')
src = src.replace("CreateWindowW(wc.lpszClassName,L\"WXXNinjaGuiden4ToolSet\",style,work.left+(work.right-work.left-774)/2,",
                  "CreateWindowW(wc.lpszClassName,L\"WXXToolsetDiag\",style,work.left-1600,")
src = src.replace('        RefreshAll();\n', '        RefreshAll();\n')  # keep
src = src.replace('    case WM_TIMER:{\n', '    case WM_TIMER:{\n        ++gDiagTimer;\n')
src = src.replace('        SetText(GetDlgItem(w,ID_OVERLAY_OPEN),gOverlayOn?L"控制器覆层：开启":L"控制器覆层：关闭");\n        return 0;',
                  '''        SetText(GetDlgItem(w,ID_OVERLAY_OPEN),gOverlayOn?L"控制器覆层：开启":L"控制器覆层：关闭");
        if(gDiagTimer>=8){
            wchar_t path[MAX_PATH],tmp[MAX_PATH];GetTempPathW(MAX_PATH,tmp);
            swprintf_s(path,L"%sWXXToolset_diag.txt",tmp);
            FILE* f=nullptr;
            if(_wfopen_s(&f,path,L"wb")==0&&f){
                fprintf(f,"timer_ticks=%d\\nsettext_actual=%d\\ndrawitem=%d\\npaint=%d\\n",gDiagTimer,gDiagSetText,gDiagDraw,gDiagPaint);
                fclose(f);
            }
            DestroyWindow(w);
        }
        return 0;''')
src = src.replace('InitializeOriginal();', '/*diag*/')
Path('build/diag_toolset.cpp').write_text(src, encoding='utf-8')
print('diag source written')
