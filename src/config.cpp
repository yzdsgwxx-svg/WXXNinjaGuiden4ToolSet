#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <cwchar>
#include <dwmapi.h>
#pragma comment(lib,"dwmapi.lib")
static HBRUSH background=CreateSolidBrush(RGB(26,26,33));
static wchar_t path[MAX_PATH];
static HWND first,second,keyFirst,keySecond;
static HFONT font;
static constexpr int ids[]={0,1,2,3,4,6};
static const wchar_t* names[]={L"双刀 / 太刀（建御名方）",L"棍 / 锤",L"螺旋剑 / 长枪（夜刀穿）",L"暗器 / 机械臂",L"黑龙丸",L"DLC 镰刀（Solitaire）"};
// Selectable trigger keys. Values are Windows virtual-key codes stored in SixSlot.ini as decimal.
struct KeyOption{int vk;const wchar_t* name;};
static const KeyOption keys[]={
    {L'Q',L"Q"},{L'E',L"E"},{L'R',L"R"},{L'F',L"F"},{L'T',L"T"},{L'G',L"G"},
    {L'Z',L"Z"},{L'X',L"X"},{L'C',L"C"},{L'V',L"V"},{L'B',L"B"},
    {L'1',L"1"},{L'2',L"2"},{L'3',L"3"},{L'4',L"4"},{L'5',L"5"},{L'6',L"6"},
    {L'7',L"7"},{L'8',L"8"},{L'9',L"9"},{L'0',L"0"},
    {VK_F1,L"F1"},{VK_F2,L"F2"},{VK_F3,L"F3"},{VK_F4,L"F4"},
    {VK_F5,L"F5"},{VK_F6,L"F6"},{VK_F7,L"F7"},{VK_F8,L"F8"},
    {VK_TAB,L"Tab"},{VK_INSERT,L"Insert"},{VK_DELETE,L"Delete"},
    {VK_HOME,L"Home"},{VK_END,L"End"},{VK_PRIOR,L"PageUp"},{VK_NEXT,L"PageDown"}};
static constexpr int keyCount=sizeof keys/sizeof keys[0];
static HWND Add(HWND parent,const wchar_t* cls,const wchar_t* text,DWORD style,int x,int y,int w,int h,int id){
    HWND child=CreateWindowExW(0,cls,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,parent,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(nullptr),nullptr);
    SendMessageW(child,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);return child;
}
static void Fill(HWND box,int weapon){
    for(int i=0;i<6;++i){SendMessageW(box,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(names[i]));if(ids[i]==weapon)SendMessageW(box,CB_SETCURSEL,i,0);}
}
static void FillKeys(HWND box,int vk){
    int sel=-1;
    for(int i=0;i<keyCount;++i){
        int index=int(SendMessageW(box,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(keys[i].name)));
        SendMessageW(box,CB_SETITEMDATA,index,keys[i].vk);
        if(keys[i].vk==vk)sel=index;
    }
    // A key typed by hand into the ini must stay visible, otherwise saving would silently replace it.
    if(sel<0&&vk>0&&vk<0x100){
        wchar_t text[32];swprintf_s(text,L"其他 (0x%02X)",vk);
        int index=int(SendMessageW(box,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(text)));
        SendMessageW(box,CB_SETITEMDATA,index,vk);sel=index;
    }
    if(sel>=0)SendMessageW(box,CB_SETCURSEL,sel,0);
}
static int SelectedKey(HWND box){
    int index=int(SendMessageW(box,CB_GETCURSEL,0,0));
    return index<0?0:int(SendMessageW(box,CB_GETITEMDATA,index,0));
}
static LRESULT CALLBACK Proc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
    switch(msg){
    case WM_CREATE:
        font=CreateFontW(-19,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei UI");
        Add(w,L"STATIC",L"6槽武器设置",0,24,18,480,32,0);
        Add(w,L"STATIC",L"按键",0,100,46,110,20,0);
        Add(w,L"STATIC",L"武器",0,220,46,280,20,0);
        Add(w,L"STATIC",L"第 5 槽",0,24,72,70,30,0);
        Add(w,L"STATIC",L"第 6 槽",0,24,124,70,30,0);
        keyFirst=Add(w,L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,100,67,110,240,104);
        first=Add(w,L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,220,67,280,240,101);
        keySecond=Add(w,L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,100,119,110,240,105);
        second=Add(w,L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,220,119,280,240,102);
        FillKeys(keyFirst,GetPrivateProfileIntW(L"Keys",L"Key5",'Q',path));
        FillKeys(keySecond,GetPrivateProfileIntW(L"Keys",L"Key6",'E',path));
        Fill(first,GetPrivateProfileIntW(L"Weapons",L"Key5",4,path));
        Fill(second,GetPrivateProfileIntW(L"Weapons",L"Key6",6,path));
        Add(w,L"STATIC",L"八云 · 已解锁武器\r\n保存后自动生效",0,24,184,475,62,0);
        Add(w,L"BUTTON",L"保存配置",BS_DEFPUSHBUTTON|WS_TABSTOP,325,280,155,40,103);
        return 0;
    case WM_COMMAND:
        if(LOWORD(wp)==103){
            int a=int(SendMessageW(first,CB_GETCURSEL,0,0)),b=int(SendMessageW(second,CB_GETCURSEL,0,0));
            if(a<0||a>=6||b<0||b>=6){MessageBoxW(w,L"请为两个槽都选择武器。",L"未保存",MB_OK);return 0;}
            int k5=SelectedKey(keyFirst),k6=SelectedKey(keySecond);
            if(k5<=0||k6<=0){MessageBoxW(w,L"请为两个槽都选择按键。",L"未保存",MB_OK);return 0;}
            if(k5==k6){MessageBoxW(w,L"两个槽不能用同一个按键，请换一个。",L"未保存",MB_OK|MB_ICONWARNING);return 0;}
            wchar_t va[8],vb[8],ka[16],kb[16];
            swprintf_s(va,L"%d",ids[a]);swprintf_s(vb,L"%d",ids[b]);
            swprintf_s(ka,L"%d",k5);swprintf_s(kb,L"%d",k6);
            bool ok=WritePrivateProfileStringW(L"Weapons",L"Key5",va,path)!=FALSE;
            ok=(WritePrivateProfileStringW(L"Weapons",L"Key6",vb,path)!=FALSE)&&ok;
            ok=(WritePrivateProfileStringW(L"Keys",L"Key5",ka,path)!=FALSE)&&ok;
            ok=(WritePrivateProfileStringW(L"Keys",L"Key6",kb,path)!=FALSE)&&ok;
            MessageBoxW(w,ok?L"配置已保存。回到游戏，按新按键测试。":L"保存失败，请检查文件夹写入权限。",ok?L"已保存":L"保存失败",MB_OK|(ok?MB_ICONINFORMATION:MB_ICONERROR));
        }return 0;
    case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:case WM_CTLCOLORLISTBOX:
        SetTextColor(reinterpret_cast<HDC>(wp),RGB(220,206,194));SetBkColor(reinterpret_cast<HDC>(wp),RGB(26,26,33));return reinterpret_cast<LRESULT>(background);
    case WM_DESTROY:DeleteObject(font);PostQuitMessage(0);return 0;
    }return DefWindowProcW(w,msg,wp,lp);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int show){
    SetProcessDPIAware();
    GetModuleFileNameW(nullptr,path,MAX_PATH);auto slash=wcsrchr(path,L'\\');if(!slash)return 1;wcscpy_s(slash+1,MAX_PATH-(slash+1-path),L"SixSlot.ini");
    WNDCLASSW wc{};wc.hInstance=instance;wc.lpfnWndProc=Proc;wc.lpszClassName=L"NG4ExtraWeaponConfig";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);wc.hbrBackground=background;wc.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(1));RegisterClassW(&wc);
    DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX;
    RECT r{0,0,510,342};AdjustWindowRect(&r,style,FALSE);
    HWND w=CreateWindowW(wc.lpszClassName,L"WXX · 6槽武器设置",style,CW_USEDEFAULT,CW_USEDEFAULT,r.right-r.left,r.bottom-r.top,nullptr,nullptr,instance,nullptr);
    BOOL dark=TRUE;DwmSetWindowAttribute(w,20,&dark,sizeof dark);
    ShowWindow(w,show);MSG msg{};while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(w,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}return 0;
}
