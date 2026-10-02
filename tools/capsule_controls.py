from pathlib import Path
p=Path('src/launcher.cpp');s=p.read_text(encoding='utf-8').replace('#include <shobjidl.h>','#include <shobjidl.h>\n#include <gdiplus.h>\n#pragma comment(lib,"gdiplus.lib")')
s=s.replace('static HWND gOverlayState;', 'static HWND gOverlayState;\nstatic bool gWeaponOn=false,gOverlayOn=false;\nstatic ULONGLONG gOverlayPending=0;\nstatic bool gOverlayRequested=false;')
s=s.replace('static void RefreshModState(){\n    DWORD pid=FindGame();','static void RefreshModState(){\n    gWeaponOn=false;\n    DWORD pid=FindGame();').replace('bool loaded=ev&&WaitForSingleObject(ev,0)==WAIT_OBJECT_0;', 'bool loaded=ev&&WaitForSingleObject(ev,0)==WAIT_OBJECT_0;gWeaponOn=loaded;')
s=s.replace('    SetWindowTextW(gModState,text.c_str());', '    SetWindowTextW(gModState,text.c_str());\n    if(gMain){SetWindowTextW(GetDlgItem(gMain,ID_MOD_LOAD),gWeaponOn?L"六槽武器：开启":L"六槽武器：关闭");InvalidateRect(GetDlgItem(gMain,ID_MOD_LOAD),nullptr,FALSE);}')
s=s.replace('        Add(w,L"BUTTON",L"加载",0,500,105,106,36,ID_MOD_LOAD);\n        Add(w,L"BUTTON",L"卸载",0,620,105,106,36,ID_MOD_STOP);', '        Add(w,L"BUTTON",L"六槽武器：关闭",0,600,105,126,36,ID_MOD_LOAD);')
s=s.replace('        Add(w,L"BUTTON",L"打开覆层",0,500,260,106,38,ID_OVERLAY_OPEN);\n        Add(w,L"BUTTON",L"关闭覆层",0,620,260,106,38,ID_OVERLAY_CLOSE);', '        Add(w,L"BUTTON",L"控制器覆层：关闭",0,600,260,126,36,ID_OVERLAY_OPEN);')
s=s.replace('        Add(w,L"BUTTON",L"已启用 · 关闭",0,574,383,152,36,ID_SWITCH_TOGGLE);','        Add(w,L"BUTTON",L"存档切换：开启",0,600,383,126,36,ID_SWITCH_TOGGLE);')
s=s.replace('        Add(w,L"BUTTON",gAutoSave?L"退出同步：开":L"退出同步：关",0,48,514,174,36,ID_AUTOSAVE);', '        Add(w,L"STATIC",L"退出同步",0,48,522,90,24,132);\n        Add(w,L"BUTTON",gAutoSave?L"退出同步：开启":L"退出同步：关闭",0,600,514,126,36,ID_AUTOSAVE);')
s=s.replace('gSwitchEnabled?L"已启用 · 关闭":L"已关闭 · 启用"', 'gSwitchEnabled?L"存档切换：开启":L"存档切换：关闭"')
s=s.replace('Label(dc,244,522,L"同步游戏已写盘的进度",', 'Label(dc,158,522,L"同步游戏已写盘的进度",')
s=s.replace('        bool down=(d->itemState&ODS_SELECTED)!=0,disabled=', '        bool down=(d->itemState&ODS_SELECTED)!=0,disabled=')
needle='        HBRUSH brush=CreateSolidBrush(down?'
pos=s.index(needle)
s=s[:pos]+'''        if(d->CtlID==ID_MOD_LOAD||d->CtlID==ID_OVERLAY_OPEN||d->CtlID==ID_SWITCH_TOGGLE||d->CtlID==ID_AUTOSAVE){
            bool on=d->CtlID==ID_MOD_LOAD?gWeaponOn:d->CtlID==ID_OVERLAY_OPEN?gOverlayOn:d->CtlID==ID_SWITCH_TOGGLE?gSwitchEnabled:gAutoSave;
            RECT label=d->rcItem;label.right=label.left+48;SetBkMode(d->hDC,TRANSPARENT);SetTextColor(d->hDC,on?RGB(218,195,173):RGB(133,125,132));SelectObject(d->hDC,gFont);
            DrawTextW(d->hDC,on?L"开启":L"关闭",-1,&label,DT_LEFT|DT_VCENTER|DT_SINGLELINE);
            Gdiplus::Graphics graphics(d->hDC);graphics.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
            Gdiplus::GraphicsPath rail;float x=60.f,y=5.f,height=26.f,width=62.f;
            rail.AddArc(x,y,height,height,90,180);rail.AddArc(x+width-height,y,height,height,270,180);rail.CloseFigure();
            Gdiplus::SolidBrush track(on?Gdiplus::Color(255,201,50,71):Gdiplus::Color(255,67,62,71));graphics.FillPath(&track,&rail);
            Gdiplus::SolidBrush knob(disabled?Gdiplus::Color(255,171,162,163):Gdiplus::Color(255,246,233,220));
            graphics.FillEllipse(&knob,x+(on?width-height:0)+3,y+3,height-6,height-6);
            if(d->itemState&ODS_FOCUS){RECT focus=d->rcItem;InflateRect(&focus,-1,-1);DrawFocusRect(d->hDC,&focus);}return TRUE;
        }
''' +s[pos:]
s=s.replace('        SetWindowTextW(gOverlayState,OverlayPid()?L"运行中 · 手柄输入与震动捕获":L"未打开");', '''        gOverlayOn=OverlayPid()!=0;
        if(gOverlayPending&&(gOverlayOn==gOverlayRequested||GetTickCount64()>gOverlayPending)){
            gOverlayPending=0;EnableWindow(GetDlgItem(w,ID_OVERLAY_OPEN),TRUE);
        }
        SetWindowTextW(gOverlayState,gOverlayPending?(gOverlayRequested?L"正在打开…":L"正在关闭…"):(gOverlayOn?L"运行中 · 手柄输入与震动捕获":L"未打开"));
        SetWindowTextW(GetDlgItem(w,ID_OVERLAY_OPEN),gOverlayOn?L"控制器覆层：开启":L"控制器覆层：关闭");
        InvalidateRect(GetDlgItem(w,ID_OVERLAY_OPEN),nullptr,FALSE);''')
s=s.replace('case ID_MOD_LOAD:DoInject();RefreshModState();return 0;', 'case ID_MOD_LOAD:if(gWeaponOn)DoStop();else DoInject();RefreshModState();return 0;')
s=s.replace('case ID_OVERLAY_OPEN:Overlay(true);return 0;', 'case ID_OVERLAY_OPEN:\n            gOverlayRequested=!gOverlayOn;Overlay(gOverlayRequested);gOverlayPending=GetTickCount64()+5000;EnableWindow(GetDlgItem(w,ID_OVERLAY_OPEN),FALSE);return 0;')
s=s.replace('gAutoSave?L"退出同步：开":L"退出同步：关"','gAutoSave?L"退出同步：开启":L"退出同步：关闭"')
s=s.replace('    SetProcessDPIAware();gExeDir=SelfDir();', '    Gdiplus::GdiplusStartupInput gdiplusInput;ULONG_PTR gdiplusToken;Gdiplus::GdiplusStartup(&gdiplusToken,&gdiplusInput,nullptr);\n    SetProcessDPIAware();gExeDir=SelfDir();')
# Success is visible in the switch, without modal dialogs.
s=s.replace('Say(L"停用额外按键",L"已停用额外按键。再点「加载 Mod」可恢复。",MB_OK|MB_ICONINFORMATION);','Sleep(30);')
s=s.replace('Say(L"加载 Mod",L"已启用额外按键。",MB_OK|MB_ICONINFORMATION);','Sleep(30);')
s=s.replace('Say(L"加载 Mod",L"已加载：按配置的按键切换额外武器。",MB_OK|MB_ICONINFORMATION);','')
p.write_text(s,encoding='utf-8')
