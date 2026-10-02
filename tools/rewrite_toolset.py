from pathlib import Path
p=Path('src/launcher.cpp');s=p.read_text(encoding='utf-8')
s=s.replace('#include <vector>','#include <vector>\n#include <dwmapi.h>\n#include <windowsx.h>\n#pragma comment(lib,"dwmapi.lib")')
s=s.replace('static ULONGLONG gLastAuto=0;', 'static bool gSwitchEnabled=true;\nstatic ULONGLONG gExitPending=0;\nstatic HWND gOverlayState;\nstatic HBRUSH gBackground=CreateSolidBrush(RGB(17,18,23)),gCard=CreateSolidBrush(RGB(26,26,33));')
s=s.replace('if(pid){CloseHandle(s);return 0;}pid=e.th32ProcessID;', 'pid=e.th32ProcessID;break;')
s=s.replace('if(_wcsicmp(d.c_str(),L"backups")==0)continue;', 'if(d!=L"原始存档" && d!=L"全成就存档")continue;')
s=s.replace('swprintf_s(buf,L"当前游戏存档：%d 个存档文件 / %.2f MB",files,double(bytes)/1048576.0);','swprintf_s(buf,L"%d 个文件 · %.2f MB",files,double(bytes)/1048576.0);').replace('L"；尚未记录来源档案"','L" · 未选择档案"').replace('L"；记录档案："','L" · "')
a=s.index('static void AutoSnapshot(');b=s.index('static void RefreshModState()',a)
s=s[:a]+'''// A single verified staging folder updates the active profile; no periodic snapshot series.
static bool CopyVerified(const std::wstring& from,const std::wstring& to,bool all=false){
    if(!CreateDirectoryW(to.c_str(),nullptr)&&GetLastError()!=ERROR_ALREADY_EXISTS)return false;
    int count=0;
    for(const auto& n:ListFiles(from)){
        if(!all&&!IsSaveFile(n))continue;
        auto src=Join(from,n.c_str()),dst=Join(to,n.c_str());std::string before,after,copy;
        if(!Sha256(src,before)||!CopyFileW(src.c_str(),dst.c_str(),FALSE)||!Sha256(src,after)||!Sha256(dst,copy)||before!=after||before!=copy)return false;
        ++count;
    }
    return count>0;
}
static bool ClearSaveFiles(const std::wstring& dir){
    for(const auto& n:ListFiles(dir))if(IsSaveFile(n)&&!DeleteFileW(Join(dir,n.c_str()).c_str()))return false;
    return true;
}
static bool SyncCurrentProfile(){
    if(FindGame() || (gCurrentProfile!=L"原始存档"&&gCurrentProfile!=L"全成就存档"))return false;
    auto stage=Join(gSavesRoot,L".pending"),previous=Join(gSavesRoot,L".previous"),dst=Join(gSavesRoot,gCurrentProfile.c_str());
    if(Exists(stage)||Exists(previous)){Log(L"上次归档未完成，保留恢复目录，请检查 saves\\\\.pending / .previous");return false;}
    const auto sig=SaveSignature();
    if(sig.empty()||!CopyVerified(gSaveDir,stage)||SaveSignature()!=sig){Log(L"归档校验失败，原档案未改动");return false;}
    bool had=Exists(dst);
    if(had&&!MoveFileW(dst.c_str(),previous.c_str()))return false;
    if(!MoveFileW(stage.c_str(),dst.c_str())){
        if(had)MoveFileW(previous.c_str(),dst.c_str());
        return false;
    }
    if(had){
        // Only our known profile save files are removed; unexpected files keep the recovery folder.
        if(ClearSaveFiles(previous))RemoveDirectoryW(previous.c_str());
    }
    Log(L"已同步到「%s」（仅包含游戏已写盘的进度）",gCurrentProfile.c_str());
    RefreshSaveState();return true;
}
''' +s[b:]
s=s.replace('L"游戏未运行。启动游戏后点「加载 Mod」。"','L"等待游戏启动"').replace('L"游戏运行中（PID %lu），Mod %s。"','L"游戏运行中 · PID %lu · %s"')
# True enabled state reported by a manual-reset event, independent from DLL residency.
s=s.replace('swprintf_s(eventName,L"Local\\\\NG4SixSlot_Start_%lu",pid);\n        HANDLE ev=OpenEventW(EVENT_MODIFY_STATE,FALSE,eventName);\n        bool loaded=ev!=nullptr;', 'swprintf_s(eventName,L"Local\\\\NG4SixSlot_Enabled_%lu",pid);\n        HANDLE ev=OpenEventW(SYNCHRONIZE,FALSE,eventName);\n        bool loaded=ev&&WaitForSingleObject(ev,0)==WAIT_OBJECT_0;').replace('loaded?L"已加载":L"未加载"','loaded?L"已启用":L"已停用"')
s=s.replace('    std::wstring src=Join(gSavesRoot,name);', '    if(!gSwitchEnabled)return;\n    if(gCurrentProfile==name){Say(L"切换存档",L"当前已经是此档案。",MB_OK);return;}\n    std::wstring src=Join(gSavesRoot,name);')
s=s.replace('    for(auto& n:ListFiles(gSaveDir)){\n        if(!IsSaveFile(n))continue;\n        std::wstring p=Join(gSaveDir,n.c_str());\n        if(!DeleteFileW(p.c_str()))Log(L"清理旧存档文件失败：%s（继续）",n.c_str());\n    }', '''    if((gCurrentProfile==L"原始存档"||gCurrentProfile==L"全成就存档")&&!SyncCurrentProfile()){
        Say(L"切换存档",L"更新当前档案失败，切换已中止。",MB_OK|MB_ICONERROR);return;
    }
    if(!ClearSaveFiles(gSaveDir)){Say(L"切换存档",L"清理旧文件失败，已停止。备份保留在 saves/backups。",MB_OK|MB_ICONERROR);return;}''')
a=s.index('/* ---------- 界面 ---------- */')
s=s[:a]+'''/* ---------- Toolset UI ---------- */
#define ID_OVERLAY_OPEN 120
#define ID_OVERLAY_CLOSE 121
#define ID_SWITCH_TOGGLE 122
#define ID_MINIMIZE 123
#define ID_CLOSE 124
static std::wstring OverlayExe(){return Join(gExeDir,L"ControllerOverlay\\\\WXXControllerOverlay.exe");}
static DWORD OverlayPid(){
    DWORD pid=0;HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);PROCESSENTRY32W e{};e.dwSize=sizeof e;
    if(snap!=INVALID_HANDLE_VALUE&&Process32FirstW(snap,&e))do{
        if(_wcsicmp(e.szExeFile,L"WXXControllerOverlay.exe"))continue;
        HANDLE h=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,e.th32ProcessID);wchar_t p[MAX_PATH];DWORD n=MAX_PATH;
        if(h){if(QueryFullProcessImageNameW(h,0,p,&n)&&!_wcsicmp(p,OverlayExe().c_str()))pid=e.th32ProcessID;CloseHandle(h);}
    }while(Process32NextW(snap,&e));
    if(snap!=INVALID_HANDLE_VALUE)CloseHandle(snap);return pid;
}
static void Overlay(bool open){
    auto exe=OverlayExe();
    if(!Exists(exe)){Say(L"控制器覆层",L"找不到 ControllerOverlay/WXXControllerOverlay.exe。",MB_OK|MB_ICONERROR);return;}
    if(!open&&!OverlayPid())return;
    auto result=ShellExecuteW(nullptr,L"open",exe.c_str(),open?nullptr:L"--close",gExeDir.c_str(),SW_SHOWNORMAL);
    if(reinterpret_cast<INT_PTR>(result)<=32)Say(L"控制器覆层",L"启动命令失败。",MB_OK|MB_ICONERROR);
}
static HWND Add(HWND parent,const wchar_t* cls,const wchar_t* text,DWORD style,int x,int y,int w,int h,int id,HFONT font=nullptr){
    if(!wcscmp(cls,L"BUTTON"))style=BS_OWNERDRAW|WS_TABSTOP;
    HWND c=CreateWindowExW(0,cls,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,parent,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(nullptr),nullptr);
    SendMessageW(c,WM_SETFONT,reinterpret_cast<WPARAM>(font?font:gFont),TRUE);return c;
}
static void Label(HDC dc,int x,int y,const wchar_t* text,COLORREF color,HFONT font){
    SetTextColor(dc,color);SetBkMode(dc,TRANSPARENT);SelectObject(dc,font);TextOutW(dc,x,y,text,int(wcslen(text)));
}
static void RefreshAll(){LoadState();RefreshProfiles();RefreshSaveState();RefreshModState();}
static LRESULT CALLBACK Proc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
    switch(msg){
    case WM_CREATE:{
        gMain=w;
        gFont=CreateFontW(-16,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        gTitleFont=CreateFontW(-24,0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        Add(w,L"BUTTON",L"—",0,670,18,38,32,ID_MINIMIZE);
        Add(w,L"BUTTON",L"×",0,716,18,38,32,ID_CLOSE);
        gModState=Add(w,L"STATIC",L"",0,48,137,420,24,ID_MODSTATE);
        Add(w,L"BUTTON",L"加载",0,500,105,106,36,ID_MOD_LOAD);
        Add(w,L"BUTTON",L"卸载",0,620,105,106,36,ID_MOD_STOP);
        Add(w,L"BUTTON",L"6槽武器设置",0,48,178,180,38,ID_CONFIG);
        gOverlayState=Add(w,L"STATIC",L"未打开",0,48,287,420,24,130);
        Add(w,L"BUTTON",L"打开覆层",0,500,260,106,38,ID_OVERLAY_OPEN);
        Add(w,L"BUTTON",L"关闭覆层",0,620,260,106,38,ID_OVERLAY_CLOSE);
        gSaveState=Add(w,L"STATIC",L"",0,48,417,460,24,ID_SAVESTATE);
        Add(w,L"BUTTON",L"已启用 · 关闭",0,574,383,152,36,ID_SWITCH_TOGGLE);
        gProfileBox=Add(w,L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,48,457,440,140,ID_PROFILE);
        SendMessageW(gProfileBox,CB_SETITEMHEIGHT,static_cast<WPARAM>(-1),30);
        Add(w,L"BUTTON",L"切换存档",0,506,454,110,38,ID_SWITCH);
        Add(w,L"BUTTON",L"档案目录",0,628,454,98,38,ID_OPENSAVES+100);
        Add(w,L"BUTTON",gAutoSave?L"退出同步：开":L"退出同步：关",0,48,514,174,36,ID_AUTOSAVE);
        Add(w,L"BUTTON",L"查看日志",0,630,590,96,32,ID_OPENSAVES);
        RefreshAll();gSaveSig=SaveSignature();gGameWasRunning=FindGame()!=0;
        SetTimer(w,1,1000,nullptr);return 0;
    }
    case WM_NCHITTEST:{
        LRESULT hit=DefWindowProcW(w,msg,wp,lp);POINT p{GET_X_LPARAM(lp),GET_Y_LPARAM(lp)};ScreenToClient(w,&p);
        if(hit==HTCLIENT&&p.y<76&&p.x<660)return HTCAPTION;return hit;
    }
    case WM_ERASEBKGND:return 1;
    case WM_PAINT:{
        PAINTSTRUCT ps;HDC dc=BeginPaint(w,&ps);RECT r;GetClientRect(w,&r);FillRect(dc,&r,gBackground);
        HPEN pen=CreatePen(PS_SOLID,1,RGB(77,46,55));auto oldPen=SelectObject(dc,pen);auto oldBrush=SelectObject(dc,gCard);
        RoundRect(dc,24,88,750,232,16,16);RoundRect(dc,24,246,750,354,16,16);RoundRect(dc,24,368,750,568,16,16);
        DrawIconEx(dc,30,19,LoadIconW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(1)),48,48,0,nullptr,DI_NORMAL);
        Label(dc,94,20,L"WXX NINJA GAIDEN 4",RGB(236,68,84),gTitleFont);
        Label(dc,96,52,L"TOOLSET",RGB(179,155,115),gFont);
        Label(dc,48,103,L"六槽武器",RGB(232,220,207),gTitleFont);
        Label(dc,48,253,L"控制器覆层",RGB(232,220,207),gTitleFont);
        Label(dc,48,383,L"存档",RGB(232,220,207),gTitleFont);
        Label(dc,244,522,L"同步游戏已写盘的进度",RGB(150,139,142),gFont);
        Label(dc,48,596,L"WXX  /  忍龙 4 工具集",RGB(135,125,126),gFont);
        SelectObject(dc,oldPen);SelectObject(dc,oldBrush);DeleteObject(pen);EndPaint(w,&ps);return 0;
    }
    case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:case WM_CTLCOLORLISTBOX:{
        HDC dc=reinterpret_cast<HDC>(wp);SetTextColor(dc,RGB(188,177,177));SetBkColor(dc,RGB(26,26,33));return reinterpret_cast<LRESULT>(gCard);
    }
    case WM_DRAWITEM:{
        auto d=reinterpret_cast<DRAWITEMSTRUCT*>(lp);if(d->CtlType!=ODT_BUTTON)break;
        bool down=(d->itemState&ODS_SELECTED)!=0,disabled=(d->itemState&ODS_DISABLED)!=0;
        HBRUSH brush=CreateSolidBrush(down?RGB(100,35,49):RGB(37,32,40));HPEN pen=CreatePen(PS_SOLID,1,RGB(99,51,63));
        auto ob=SelectObject(d->hDC,brush);auto op=SelectObject(d->hDC,pen);RoundRect(d->hDC,d->rcItem.left,d->rcItem.top,d->rcItem.right,d->rcItem.bottom,8,8);
        wchar_t t[128];GetWindowTextW(d->hwndItem,t,128);SetTextColor(d->hDC,disabled?RGB(100,94,98):RGB(226,211,195));SetBkMode(d->hDC,TRANSPARENT);SelectObject(d->hDC,gFont);DrawTextW(d->hDC,t,-1,&d->rcItem,DT_CENTER|DT_VCENTER|DT_SINGLELINE);
        if(d->itemState&ODS_FOCUS){RECT f=d->rcItem;InflateRect(&f,-4,-4);DrawFocusRect(d->hDC,&f);}
        SelectObject(d->hDC,ob);SelectObject(d->hDC,op);DeleteObject(brush);DeleteObject(pen);return TRUE;
    }
    case WM_TIMER:{
        bool running=FindGame()!=0;RefreshModState();
        SetWindowTextW(gOverlayState,OverlayPid()?L"运行中 · 手柄输入与震动捕获":L"未打开");
        if(gGameWasRunning&&!running&&gAutoSave)gExitPending=GetTickCount64()+1500;
        gGameWasRunning=running;
        if(gExitPending&&GetTickCount64()>=gExitPending){
            gExitPending=0;if(!running&&gAutoSave)SyncCurrentProfile();
        }return 0;
    }
    case WM_COMMAND:
        switch(LOWORD(wp)){
        case ID_PROFILE:if(HIWORD(wp)==CBN_DROPDOWN){LoadState();RefreshProfiles();RefreshSaveState();}return 0;
        case ID_MOD_LOAD:DoInject();RefreshModState();return 0;
        case ID_MOD_STOP:DoStop();RefreshModState();return 0;
        case ID_CONFIG:ShellExecuteW(w,L"open",Join(gExeDir,L"SixSlotConfig.exe").c_str(),nullptr,gExeDir.c_str(),SW_SHOWNORMAL);return 0;
        case ID_OVERLAY_OPEN:Overlay(true);return 0;
        case ID_OVERLAY_CLOSE:Overlay(false);return 0;
        case ID_SWITCH:SwitchToProfile();return 0;
        case ID_SWITCH_TOGGLE:
            gSwitchEnabled=!gSwitchEnabled;EnableWindow(gProfileBox,gSwitchEnabled);EnableWindow(GetDlgItem(w,ID_SWITCH),gSwitchEnabled);
            SetWindowTextW(GetDlgItem(w,ID_SWITCH_TOGGLE),gSwitchEnabled?L"已启用 · 关闭":L"已关闭 · 启用");return 0;
        case ID_AUTOSAVE:
            gAutoSave=!gAutoSave;gExitPending=0;SetWindowTextW(GetDlgItem(w,ID_AUTOSAVE),gAutoSave?L"退出同步：开":L"退出同步：关");
            WritePrivateProfileStringW(L"Toolset",L"ExitSync",gAutoSave?L"1":L"0",Join(gExeDir,L"SixSlot.ini").c_str());return 0;
        case ID_OPENSAVES+100:ShellExecuteW(w,L"open",gSavesRoot.c_str(),nullptr,nullptr,SW_SHOWNORMAL);return 0;
        case ID_OPENSAVES:ShellExecuteW(w,L"open",gLogFile.c_str(),nullptr,gExeDir.c_str(),SW_SHOWNORMAL);return 0;
        case ID_MINIMIZE:ShowWindow(w,SW_MINIMIZE);return 0;
        case ID_CLOSE:DestroyWindow(w);return 0;
        }return 0;
    case WM_DESTROY:DeleteObject(gFont);DeleteObject(gTitleFont);PostQuitMessage(0);return 0;
    }return DefWindowProcW(w,msg,wp,lp);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR cmdline,int show){
    SetProcessDPIAware();gExeDir=SelfDir();gSavesRoot=Join(gExeDir,L"saves");gSaveDir=LocalSaveDir();
    gStateFile=Join(gSavesRoot,L"current.txt");gLogFile=Join(gExeDir,L"WXXToolset.log");
    gAutoSave=GetPrivateProfileIntW(L"Toolset",L"ExitSync",1,Join(gExeDir,L"SixSlot.ini").c_str())!=0;
    std::wstring args=cmdline?cmdline:L"";
    if(args==L"--stop"){DoStop();return 0;}
    if(args==L"--overlay-open"){Overlay(true);return 0;}
    if(args==L"--overlay-close"){Overlay(false);return 0;}
    HWND existing=FindWindowW(L"WXXNinjaGuiden4ToolSet",nullptr);if(existing){ShowWindow(existing,SW_RESTORE);SetForegroundWindow(existing);return 0;}
    WNDCLASSW wc{};wc.hInstance=instance;wc.lpfnWndProc=Proc;wc.lpszClassName=L"WXXNinjaGuiden4ToolSet";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);wc.hbrBackground=gBackground;wc.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(1));RegisterClassW(&wc);
    DWORD style=WS_POPUP|WS_MINIMIZEBOX|WS_SYSMENU;RECT work;SystemParametersInfoW(SPI_GETWORKAREA,0,&work,0);
    HWND w=CreateWindowW(wc.lpszClassName,L"WXXNinjaGuiden4ToolSet",style,work.left+(work.right-work.left-774)/2,work.top+(work.bottom-work.top-648)/2,774,648,nullptr,nullptr,instance,nullptr);
    int corner=2;DwmSetWindowAttribute(w,33,&corner,sizeof corner);
    ShowWindow(w,show);MSG msg{};while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(w,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}return 0;
}
'''
p.write_text(s,encoding='utf-8')
p=Path('src/mod.cpp');s=p.read_text(encoding='utf-8');a=s.index('// 主动保存');b=s.index('struct Context',a);s=s[:a]+s[b:];a=s.index('/* 存档线程');b=s.index('static bool __fastcall SelectHook',a);s=s[:a]+s[b:]
s=s.replace('stopName[96],startName[96],saveName[96]', 'stopName[96],startName[96],stateName[96]')
s=s.replace('swprintf_s(saveName,L"Local\\\\NG4SixSlot_Save_%lu",GetCurrentProcessId());','swprintf_s(stateName,L"Local\\\\NG4SixSlot_Enabled_%lu",GetCurrentProcessId());')
a=s.index('    HANDLE save=CreateEventW');b=s.index('    bool last5',a);s=s[:a]+'    HANDLE state=CreateEventW(nullptr,TRUE,TRUE,stateName);\n'+s[b:]
s=s.replace('    ULONGLONG lastUpdateSeen=0,idleSince=0,lastAutoSave=0;\n','').replace('enabled=false;request=0;', 'enabled=false;if(state)ResetEvent(state);request=0;').replace('enabled=true;request=0;', 'enabled=true;if(state)SetEvent(state);request=0;')
s=s.replace('        if(save && WaitForSingleObject(save,0)==WAIT_OBJECT_0)RequestSave();\n','')
s=re.sub(r'        \(void\)lastUpdateSeen;.*?\n','',s) if False else s
s=s.replace('        (void)lastUpdateSeen;(void)idleSince;(void)lastAutoSave;\n','')
a=s.index('            if(requestPath[0]');b=s.index('\n        }',a);s=s[:a]+s[b:]
p.write_text(s,encoding='utf-8')
