#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <tlhelp32.h>
#include <shellapi.h>
#include <bcrypt.h>
#include <cwchar>
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <string>
#include <vector>
#include <dwmapi.h>
#include <windowsx.h>
#include <objidl.h>
#include <gdiplus.h>
#pragma comment(lib,"gdiplus.lib")
#pragma comment(lib,"dwmapi.lib")
#pragma comment(lib,"bcrypt.lib")
#pragma comment(lib,"shell32.lib")

/* 面板程序：加载/停用注入 Mod + 存档档案切换。取代原来的控制台 launcher。
   存档目录：<exe>\saves\<档案名>\，切换前把当前游戏存档完整备份到 <exe>\saves\backups\，
   备份只增不删；脚本工具 tools/save_manager.py 仍可用于命令行校验。
   写盘只有一条路：游戏里按 F10（SixSlot.dll 的 [Save] TestKey），面板不再有存档开关。 */

#define ID_MOD_LOAD 101
#define ID_MOD_STOP 102
#define ID_CONFIG 103
#define ID_PROFILE 104
#define ID_SWITCH 105
#define ID_NEWPROFILE 106
#define ID_REFRESH 107
#define ID_LOG 108
#define ID_OPENSAVES 109
#define ID_MODSTATE 110
#define ID_SAVESTATE 111

static HWND gLog,gProfileBox,gModState,gSaveState,gF10State;
static HFONT gFont,gTitleFont;
static std::wstring gExeDir,gSavesRoot,gSaveDir,gStateFile,gLogFile,gCurrentProfile;
static const wchar_t* kGameExe=L"NINJAGAIDEN4-Steam.exe";
/* 存档同步只在切换存档时进行：切换前把游戏当前存档写回当前档案。 */
/* 两个开关的状态记在 SixSlot.ini 里，打开面板按记忆恢复：
   六槽武器 = [Toolset] WeaponSwitch（开着就在游戏运行时主动注入），
   F10 存档 = [Save] TestKey（0 = 关闭，默认 F10=121）。
   开关显示的是"记住的意图"，gModLoaded/gModEnabled 才是游戏里的真实状态。 */
static bool gWeaponOn=false,gF10On=true,gModLoaded=false,gModEnabled=false;
static HWND gOverlayState;
static bool gOverlayOn=false;
static ULONGLONG gOverlayPending=0;
static DWORD gAutoInjectPid=0;   /* 已经自动注入过的游戏进程：失败只记日志，重启游戏后再试 */
static HBRUSH gBackground=CreateSolidBrush(RGB(17,18,23)),gCard=CreateSolidBrush(RGB(26,26,33));
static const char* kGameHash="3e3ecfe254c33aac2d906126f3b7a0ee9ac92e01ec414f6b7f77ec2f79e8c83a";

/* ---------- 基础工具 ---------- */
static std::wstring Join(const std::wstring& base,const wchar_t* name){
    std::wstring s=base;
    if(!s.empty()&&s.back()!=L'\\')s+=L'\\';
    s+=name;return s;
}
static bool Exists(const std::wstring& p){return GetFileAttributesW(p.c_str())!=INVALID_FILE_ATTRIBUTES;}
static std::wstring SelfDir(){
    wchar_t b[MAX_PATH];GetModuleFileNameW(nullptr,b,MAX_PATH);std::wstring s=b;
    size_t i=s.find_last_of(L'\\');return i==std::wstring::npos?std::wstring(L"."):s.substr(0,i);
}
static std::wstring LocalSaveDir(){
    wchar_t* v=nullptr;size_t n=0;_wdupenv_s(&v,&n,L"LOCALAPPDATA");
    std::wstring s=v?v:L"C:\\";free(v);return Join(s,L"NINJAGAIDEN4");
}
/* 开关状态与 mod 共用一份 ini：面板写、mod 每秒热重载，改开关不用重启游戏。 */
static std::wstring IniPath(){return Join(gExeDir,L"SixSlot.ini");}
static void Log(const wchar_t* fmt,...){
    wchar_t line[2048];va_list a;va_start(a,fmt);_vsnwprintf_s(line,_TRUNCATE,fmt,a);va_end(a);
    SYSTEMTIME t;GetLocalTime(&t);
    wchar_t stamped[2200];swprintf_s(stamped,L"%02d:%02d:%02d %s",t.wHour,t.wMinute,t.wSecond,line);
    if(gLog){
        SendMessageW(gLog,EM_SETREADONLY,FALSE,0);
        int len=GetWindowTextLengthW(gLog);
        SendMessageW(gLog,EM_SETSEL,len,len);
        std::wstring text=stamped;text+=L"\r\n";
        SendMessageW(gLog,EM_REPLACESEL,FALSE,reinterpret_cast<LPARAM>(text.c_str()));
        SendMessageW(gLog,EM_SCROLLCARET,0,0);
        SendMessageW(gLog,EM_SETREADONLY,TRUE,0);
    }
    FILE* f=nullptr;
    if(!gLogFile.empty()&&_wfopen_s(&f,gLogFile.c_str(),L"ab")==0&&f){
        char utf8[4096];int n=WideCharToMultiByte(CP_UTF8,0,stamped,-1,utf8,sizeof utf8,nullptr,nullptr);
        if(n>1)fwrite(utf8,1,size_t(n-1),f);
        fputc('\n',f);fclose(f);
    }
}
static void Say(const wchar_t* title,const std::wstring& text,UINT flags){
    MessageBoxW(nullptr,text.c_str(),title,flags);
}

/* ---------- 文件与哈希 ---------- */
static bool Sha256(const std::wstring& path,std::string& hex){
    HANDLE f=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,0,nullptr);
    if(f==INVALID_HANDLE_VALUE)return false;
    BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE h=nullptr;
    bool ok=BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)==0;
    if(ok)ok=BCryptCreateHash(alg,&h,nullptr,0,nullptr,0,0)==0;
    unsigned char buf[65536],digest[32];DWORD n=0;
    while(ok){if(!ReadFile(f,buf,sizeof buf,&n,nullptr)){ok=false;break;}if(!n)break;ok=BCryptHashData(h,buf,n,0)==0;}
    if(ok)ok=BCryptFinishHash(h,digest,32,0)==0;
    if(h)BCryptDestroyHash(h);if(alg)BCryptCloseAlgorithmProvider(alg,0);CloseHandle(f);
    char out[65]{};for(int i=0;ok&&i<32;++i)sprintf_s(out+i*2,3,"%02x",digest[i]);
    if(ok)hex=out;
    return ok;
}
static std::vector<std::wstring> ListFiles(const std::wstring& dir){
    std::vector<std::wstring> out;WIN32_FIND_DATAW fd{};
    HANDLE h=FindFirstFileW(Join(dir,L"*").c_str(),&fd);
    if(h==INVALID_HANDLE_VALUE)return out;
    do{if(!(fd.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY))out.push_back(fd.cFileName);}while(FindNextFileW(h,&fd));
    FindClose(h);return out;
}
static std::vector<std::wstring> ListDirs(const std::wstring& dir){
    std::vector<std::wstring> out;WIN32_FIND_DATAW fd{};
    HANDLE h=FindFirstFileW(Join(dir,L"*").c_str(),&fd);
    if(h==INVALID_HANDLE_VALUE)return out;
    do{
        if((fd.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&wcscmp(fd.cFileName,L".")&&wcscmp(fd.cFileName,L".."))out.push_back(fd.cFileName);
    }while(FindNextFileW(h,&fd));
    FindClose(h);return out;
}
static bool IsSaveFile(const std::wstring& n){
    if(n==L"GameData.dat"||n==L"SystemData.vdf")return true;
    if(n.size()>13&&_wcsnicmp(n.c_str(),L"SlotData_",9)==0&&_wcsicmp(n.c_str()+n.size()-4,L".dat")==0)return true;
    return false;
}

/* ---------- Mod 注入 ---------- */
static DWORD FindGame(){
    HANDLE s=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);
    if(s==INVALID_HANDLE_VALUE)return 0;
    PROCESSENTRY32W e{};e.dwSize=sizeof e;DWORD pid=0;
    if(Process32FirstW(s,&e))do{
        if(!_wcsicmp(e.szExeFile,kGameExe)){pid=e.th32ProcessID;break;}
    }while(Process32NextW(s,&e));
    CloseHandle(s);return pid;
}
static void DoStop(bool silent=false){
    DWORD pid=FindGame();
    if(!pid){Log(L"停用：游戏没在运行");if(!silent)Say(L"停用额外按键",L"游戏没在运行，无需停用。",MB_OK);return;}
    wchar_t name[96];swprintf_s(name,L"Local\\NG4SixSlot_Stop_%lu",pid);
    HANDLE ev=OpenEventW(EVENT_MODIFY_STATE,FALSE,name);
    if(ev){SetEvent(ev);CloseHandle(ev);Log(L"已发送停用指令（PID %lu）",pid);Sleep(30);}
    else{Log(L"停用失败：Mod 未加载（PID %lu）",pid);if(!silent)Say(L"停用额外按键",L"Mod 尚未加载。",MB_OK|MB_ICONWARNING);}
}
/* 开关（把游戏里的 Mod 切到开/关）：Mod 已在游戏里时只发事件，不重新注入。 */
static bool SendModSwitch(DWORD pid,bool on){
    wchar_t name[96];swprintf_s(name,L"Local\\NG4SixSlot_%s_%lu",on?L"Start":L"Stop",pid);
    HANDLE ev=OpenEventW(EVENT_MODIFY_STATE,FALSE,name);
    if(!ev)return false;
    SetEvent(ev);CloseHandle(ev);
    Log(L"已发送%s指令（PID %lu）",on?L"启用":L"停用",pid);
    return true;
}
static void DoInject(bool silent=false){
    DWORD pid=FindGame();
    if(!pid){Log(L"加载：找不到 %s",kGameExe);if(!silent)Say(L"加载 Mod",L"请先启动忍龙 4（Steam 版），再点「加载 Mod」。",MB_OK|MB_ICONWARNING);return;}
    wchar_t eventName[96];swprintf_s(eventName,L"Local\\NG4SixSlot_Start_%lu",pid);
    HANDLE ev=OpenEventW(EVENT_MODIFY_STATE,FALSE,eventName);
    if(ev){SetEvent(ev);CloseHandle(ev);Log(L"Mod 已在游戏中，已发送启用指令（PID %lu）",pid);Sleep(30);return;}
    std::wstring dll=Join(gExeDir,L"SixSlot.dll");
    if(!Exists(dll)){Log(L"加载：找不到 %s",dll.c_str());if(!silent)Say(L"加载 Mod",L"找不到同目录的 SixSlot.dll。",MB_OK|MB_ICONERROR);return;}
    HANDLE process=OpenProcess(PROCESS_CREATE_THREAD|PROCESS_QUERY_INFORMATION|PROCESS_VM_OPERATION|PROCESS_VM_WRITE|PROCESS_VM_READ,FALSE,pid);
    if(!process){wchar_t m[160];swprintf_s(m,L"无法打开游戏进程，错误 %lu。",GetLastError());Log(L"%s",m);if(!silent)Say(L"加载 Mod",m,MB_OK|MB_ICONERROR);return;}
    wchar_t exe[MAX_PATH];DWORD chars=MAX_PATH;
    std::string hash;
    bool ok=QueryFullProcessImageNameW(process,0,exe,&chars)&&Sha256(exe,hash)&&hash==kGameHash;
    if(!ok){
        Log(L"加载：游戏版本与已验证配置不匹配，未写入进程");
        if(!silent)Say(L"加载 Mod",L"游戏版本与已验证配置不匹配；未写入游戏进程。",MB_OK|MB_ICONERROR);
        CloseHandle(process);return;
    }
    /* LoadLibraryW 在目标进程里可能被转发，用实际 owner 模块解析远程地址。 */
    auto load=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"LoadLibraryW");
    HMODULE owner=nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(load),&owner);
    wchar_t ownerPath[MAX_PATH];GetModuleFileNameW(owner,ownerPath,MAX_PATH);
    const wchar_t* ownerName=wcsrchr(ownerPath,L'\\')+1;
    uintptr_t remoteOwner=0;bool alreadyLoaded=false;
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);
    MODULEENTRY32W m{};m.dwSize=sizeof m;
    if(Module32FirstW(snap,&m))do{
        if(!_wcsicmp(m.szModule,ownerName))remoteOwner=reinterpret_cast<uintptr_t>(m.modBaseAddr);
        if(!_wcsicmp(m.szModule,L"SixSlot.dll"))alreadyLoaded=true;
    }while(Module32NextW(snap,&m));
    CloseHandle(snap);
    if(alreadyLoaded){
        Log(L"加载：DLL 已加载但未就绪（PID %lu）",pid);
        if(!silent)Say(L"加载 Mod",L"DLL 已加载但未就绪。请检查 SixSlot.log；要重新加载需重启游戏。",MB_OK|MB_ICONWARNING);
        CloseHandle(process);return;
    }
    if(!remoteOwner){Log(L"加载：无法定位 Windows 加载器");if(!silent)Say(L"加载 Mod",L"无法定位 Windows 加载器。",MB_OK|MB_ICONERROR);CloseHandle(process);return;}
    auto remoteLoad=reinterpret_cast<LPTHREAD_START_ROUTINE>(remoteOwner+reinterpret_cast<uintptr_t>(load)-reinterpret_cast<uintptr_t>(owner));
    SIZE_T bytes=(wcslen(dll.c_str())+1)*sizeof(wchar_t),written=0;
    void* allocation=VirtualAllocEx(process,nullptr,bytes,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!allocation||!WriteProcessMemory(process,allocation,dll.c_str(),bytes,&written)||written!=bytes){
        wchar_t msg[160];swprintf_s(msg,L"加载准备失败，错误 %lu。",GetLastError());Log(L"%s",msg);if(!silent)Say(L"加载 Mod",msg,MB_OK|MB_ICONERROR);
        if(allocation)VirtualFreeEx(process,allocation,0,MEM_RELEASE);
        CloseHandle(process);return;
    }
    HANDLE thread=CreateRemoteThread(process,nullptr,0,remoteLoad,allocation,0,nullptr);
    if(!thread){
        wchar_t msg[160];swprintf_s(msg,L"加载失败，错误 %lu。",GetLastError());Log(L"%s",msg);if(!silent)Say(L"加载 Mod",msg,MB_OK|MB_ICONERROR);
        VirtualFreeEx(process,allocation,0,MEM_RELEASE);CloseHandle(process);return;
    }
    DWORD wait=WaitForSingleObject(thread,10000);
    if(wait==WAIT_OBJECT_0)VirtualFreeEx(process,allocation,0,MEM_RELEASE);
    CloseHandle(thread);CloseHandle(process);
    if(wait!=WAIT_OBJECT_0){Log(L"加载仍未完成，未重复加载");if(!silent)Say(L"加载 Mod",L"加载仍未完成，未重复加载。请查看 SixSlot.log。",MB_OK|MB_ICONWARNING);return;}
    for(int i=0;i<100;++i){
        ev=OpenEventW(EVENT_MODIFY_STATE,FALSE,eventName);
        if(ev){CloseHandle(ev);Log(L"Mod 已加载（PID %lu）",pid);return;}
        Sleep(50);
    }
    Log(L"未收到就绪信号（PID %lu）",pid);
    if(!silent)Say(L"加载 Mod",L"未收到就绪信号，请查看 SixSlot.log。",MB_OK|MB_ICONWARNING);
}

/* ---------- 存档切换 ---------- */
static HWND gMain;
/* 内容滚动容器：四张卡片都挂在 gScrollBox 里，功能变多时自动出现纵向滚动条。
   控件坐标一律用相对容器的坐标（= 原来的绝对 y 减 kScrollTop），滚动由 ScrollWindowEx 搬。 */
static HWND gScrollBox=nullptr;
static constexpr int kScrollTop=80;
static HWND Ctl(int id){
    if(gScrollBox){HWND child=GetDlgItem(gScrollBox,id);if(child)return child;}
    return gMain?GetDlgItem(gMain,id):nullptr;
}
static void LoadState(){
    gCurrentProfile.clear();
    FILE* f=nullptr;
    if(_wfopen_s(&f,gStateFile.c_str(),L"rb")==0&&f){
        char buf[512]{};size_t n=fread(buf,1,sizeof buf-1,f);fclose(f);
        wchar_t w[512]{};MultiByteToWideChar(CP_UTF8,0,buf,int(n),w,512);
        gCurrentProfile=w;
        while(!gCurrentProfile.empty()&&(gCurrentProfile.back()==L'\n'||gCurrentProfile.back()==L'\r'))gCurrentProfile.pop_back();
    }
}
static void SaveState(const std::wstring& name){
    CreateDirectoryW(gSavesRoot.c_str(),nullptr);
    FILE* f=nullptr;
    if(_wfopen_s(&f,gStateFile.c_str(),L"wb")==0&&f){
        char utf8[512];int n=WideCharToMultiByte(CP_UTF8,0,name.c_str(),-1,utf8,sizeof utf8,nullptr,nullptr);
        if(n>1)fwrite(utf8,1,size_t(n-1),f);
        fclose(f);
    }
    gCurrentProfile=name;
}
static void RefreshProfiles(){
    SendMessageW(gProfileBox,CB_RESETCONTENT,0,0);
    int match=-1,index=0;
    for(auto& d:ListDirs(gSavesRoot)){
        if(d!=L"原始存档" && d!=L"全成就存档")continue;
        SendMessageW(gProfileBox,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(d.c_str()));
        if(!gCurrentProfile.empty()&&_wcsicmp(d.c_str(),gCurrentProfile.c_str())==0)match=index;
        ++index;
    }
    SendMessageW(gProfileBox,CB_SETCURSEL,match>=0?match:0,0);
    if(index==0)Log(L"saves 目录里没有档案：%s",gSavesRoot.c_str());
}
/* ---------- 避免每秒重绘 ---------- */
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
static void RefreshSaveState(){
    std::wstring text;
    if(!Exists(gSaveDir))text=L"游戏存档目录不存在："+gSaveDir;
    else{
        int files=0;ULONGLONG bytes=0;
        for(auto& n:ListFiles(gSaveDir)){
            if(!IsSaveFile(n))continue;
            ++files;
            WIN32_FILE_ATTRIBUTE_DATA a{};
            if(GetFileAttributesExW(Join(gSaveDir,n.c_str()).c_str(),GetFileExInfoStandard,&a))bytes+=(ULONGLONG(a.nFileSizeHigh)<<32)|a.nFileSizeLow;
        }
        wchar_t buf[320];
        swprintf_s(buf,L"%d 个文件 · %.2f MB",files,double(bytes)/1048576.0);
        text=buf;
        text+=gCurrentProfile.empty()?L" · 未选择档案":(L" · "+gCurrentProfile);
    }
    SetText(gSaveState,text);
}
/* 存档文件的指纹：名字 + 大小 + 修改时间。够用来判断游戏是否刚写过存档。 */
static std::wstring SaveSignature(){
    std::wstring sig;
    for(auto& n:ListFiles(gSaveDir)){
        if(!IsSaveFile(n))continue;
        WIN32_FILE_ATTRIBUTE_DATA a{};
        if(GetFileAttributesExW(Join(gSaveDir,n.c_str()).c_str(),GetFileExInfoStandard,&a)){
            wchar_t b[192];
            swprintf_s(b,L"%s:%llu:%llu;",n.c_str(),
                (ULONGLONG(a.nFileSizeHigh)<<32)|a.nFileSizeLow,
                (ULONGLONG(a.ftLastWriteTime.dwHighDateTime)<<32)|a.ftLastWriteTime.dwLowDateTime);
            sig+=b;
        }
    }
    return sig;
}
// A single verified staging folder updates the active profile; no periodic snapshot series.
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
    if(Exists(stage)||Exists(previous)){Log(L"上次归档未完成，保留恢复目录，请检查 saves\\.pending / .previous");return false;}
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
static void InitializeOriginal(){
    if(FindGame()||!gCurrentProfile.empty()||Exists(Join(gSavesRoot,L"原始存档")))return;
    if(SaveSignature().empty())return;
    CreateDirectoryW(gSavesRoot.c_str(),nullptr);
    auto dst=Join(gSavesRoot,L"原始存档"),stage=Join(gSavesRoot,L".initial");
    if(Exists(stage)){Log(L"初始备份未完成，请检查 saves/.initial");return;}
    auto sig=SaveSignature();
    if(CopyVerified(gSaveDir,stage)&&sig==SaveSignature()&&MoveFileW(stage.c_str(),dst.c_str())){
        SaveState(L"原始存档");Log(L"已建立此 Windows 用户的原始存档");
    }
}
/* Windows 会取用户令牌和 EXE 文件完整性级别的较低者作为新进程级别。
   输出目录继承 Low 标签时，普通启动也会变成 Low；修复 dist 的文件标签，
   不要用管理员运行或禁用 Electron 沙箱掩盖这个问题。 */
static int gIntegrityLevel=1;   /* 0 = 低，1 = 中，2 = 高 */
static bool gLowIntegrity=false;
static bool gHighIntegrity=false;
static int SelfIntegrityLevel(){
    int level=1;
    HANDLE token=nullptr;
    if(OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token)){
        DWORD size=0;GetTokenInformation(token,TokenIntegrityLevel,nullptr,0,&size);
        if(size){
            auto label=static_cast<TOKEN_MANDATORY_LABEL*>(malloc(size));
            if(label&&GetTokenInformation(token,TokenIntegrityLevel,label,size,&size)){
                /* SID: Revision(1) + SubAuthorityCount(1) + Authority(6) + SubAuthority[](4)。 */
                const unsigned char* sid=reinterpret_cast<const unsigned char*>(label->Label.Sid);
                const unsigned char count=sid[1];
                if(count){
                    const DWORD rid=*reinterpret_cast<const DWORD*>(sid+8+(count-1)*4);
                    if(rid<SECURITY_MANDATORY_MEDIUM_RID)level=0;
                    else if(rid>=SECURITY_MANDATORY_HIGH_RID)level=2;
                }
            }
            free(label);
        }
        CloseHandle(token);
    }
    return level;
}
static void RefreshModState(){
    gModLoaded=gModEnabled=false;
    DWORD pid=FindGame();
    std::wstring text;
    if(!pid)text=gLowIntegrity?L"权限不足 · 运行 Repair-Permissions.cmd 后重新打开":L"等待游戏启动";
    else{
        wchar_t buf[256];
        wchar_t eventName[96];swprintf_s(eventName,L"Local\\NG4SixSlot_Enabled_%lu",pid);
        HANDLE ev=OpenEventW(SYNCHRONIZE,FALSE,eventName);
        if(ev){gModLoaded=true;gModEnabled=WaitForSingleObject(ev,0)==WAIT_OBJECT_0;CloseHandle(ev);}
        swprintf_s(buf,L"游戏运行中 · PID %lu · %s",pid,!gModLoaded?L"未注入":(gModEnabled?L"已启用":L"已停用"));
        text=buf;
    }
    SetText(gModState,text);
    SetText(Ctl(ID_MOD_LOAD),gWeaponOn?L"六槽武器：开启":L"六槽武器：关闭");
}
/* F10 存档的状态行：只读游戏自己写的存档时间，按一下 F10 一秒内这里会变。 */
static void RefreshF10State(){
    ULONGLONG newest=0;
    for(const wchar_t* name:{L"GameData.dat",L"SystemData.vdf"}){
        WIN32_FILE_ATTRIBUTE_DATA a{};
        if(!GetFileAttributesExW(Join(gSaveDir,name).c_str(),GetFileExInfoStandard,&a))continue;
        const ULONGLONG stamp=(ULONGLONG(a.ftLastWriteTime.dwHighDateTime)<<32)|a.ftLastWriteTime.dwLowDateTime;
        if(stamp>newest)newest=stamp;
    }
    wchar_t buf[320];
    if(!newest)wcscpy_s(buf,L"还没写过存档");
    else{
        FILETIME utc{},local{};SYSTEMTIME t{};
        utc.dwLowDateTime=DWORD(newest&0xffffffff);utc.dwHighDateTime=DWORD(newest>>32);
        if(FileTimeToLocalFileTime(&utc,&local)&&FileTimeToSystemTime(&local,&t))
            swprintf_s(buf,L"最近存档 %02d:%02d:%02d",t.wHour,t.wMinute,t.wSecond);
        else wcscpy_s(buf,L"最近存档时间未知");
    }
    if(FindGame())wcscat_s(buf,L" · 游戏运行中");
    SetText(gF10State,buf);
}
static void SwitchToProfile(){
    int sel=int(SendMessageW(gProfileBox,CB_GETCURSEL,0,0));
    if(sel==CB_ERR){Say(L"切换存档",L"先在列表里选一个存档档案。",MB_OK|MB_ICONWARNING);return;}
    wchar_t name[256]{};SendMessageW(gProfileBox,CB_GETLBTEXT,sel,reinterpret_cast<LPARAM>(name));
    if(FindGame()){Say(L"切换存档",L"游戏正在运行。请在游戏里正常退出到桌面后再切换存档。",MB_OK|MB_ICONWARNING);return;}
    if(gCurrentProfile==name){Say(L"切换存档",L"当前已经是此档案。",MB_OK);return;}
    std::wstring src=Join(gSavesRoot,name);
    std::vector<std::wstring> files=ListFiles(src);
    int saveCount=0;for(auto& n:files)if(IsSaveFile(n))++saveCount;
    if(!saveCount){Say(L"切换存档",L"这个档案里没有可用的存档文件。",MB_OK|MB_ICONERROR);return;}
    std::wstring ask=L"把游戏存档切换为「"+std::wstring(name)+L"」？\r\n\r\n";
    ask+=L"切换前会把当前存档完整备份到 saves\\backups\\，备份只增不删，随时可以取回。";
    if(MessageBoxW(nullptr,ask.c_str(),L"切换存档",MB_YESNO|MB_ICONQUESTION)!=IDYES)return;

    SYSTEMTIME t;GetLocalTime(&t);
    wchar_t stamp[64];swprintf_s(stamp,L"%04d%02d%02d-%02d%02d%02d",t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond);
    std::wstring backups=Join(gSavesRoot,L"backups");
    CreateDirectoryW(gSavesRoot.c_str(),nullptr);CreateDirectoryW(backups.c_str(),nullptr);
    std::wstring bak=Join(backups,(std::wstring(stamp)+L"_"+(gCurrentProfile.empty()?L"未归档":gCurrentProfile)).c_str());
    CreateDirectoryW(bak.c_str(),nullptr);

    if(!Exists(gSaveDir))CreateDirectoryW(gSaveDir.c_str(),nullptr);
    int backed=0;
    for(auto& n:ListFiles(gSaveDir)){
        std::wstring s=Join(gSaveDir,n.c_str()),d=Join(bak,n.c_str());
        std::string h1,h2;
        if(!CopyFileW(s.c_str(),d.c_str(),FALSE)||!Sha256(s,h1)||!Sha256(d,h2)||h1!=h2){
            Log(L"备份失败：%s；已中止切换，游戏存档未改动",n.c_str());
            Say(L"切换存档",L"备份当前存档失败，已中止切换，你的存档没有被改动。",MB_OK|MB_ICONERROR);
            return;
        }
        ++backed;
    }
    Log(L"已备份当前存档 %d 个文件 → %s",backed,bak.c_str());

    if((gCurrentProfile==L"原始存档"||gCurrentProfile==L"全成就存档")&&!SyncCurrentProfile()){
        Say(L"切换存档",L"更新当前档案失败，切换已中止。",MB_OK|MB_ICONERROR);return;
    }
    if(!ClearSaveFiles(gSaveDir)){Say(L"切换存档",L"清理旧文件失败，已停止。备份保留在 saves/backups。",MB_OK|MB_ICONERROR);return;}
    int copied=0;
    for(auto& n:files){
        if(!IsSaveFile(n)){Log(L"跳过档案里的非存档文件：%s",n.c_str());continue;}
        std::wstring s=Join(src,n.c_str()),d=Join(gSaveDir,n.c_str());
        std::string h1,h2;
        if(!CopyFileW(s.c_str(),d.c_str(),FALSE)||!Sha256(s,h1)||!Sha256(d,h2)||h1!=h2){
            Log(L"写入失败：%s",n.c_str());
            Say(L"切换存档",(L"写入 "+n+L" 失败或校验不一致。\r\n当前存档已备份在：\r\n"+bak).c_str(),MB_OK|MB_ICONERROR);
            return;
        }
        ++copied;
    }
    SaveState(name);
    Log(L"存档已切换为「%s」：%d 个文件，备份 %s",name,copied,bak.c_str());
    RefreshSaveState();
    Say(L"切换存档",(L"已切换到「"+std::wstring(name)+L"」。\r\n\r\n本次备份：\r\n"+bak).c_str(),MB_OK|MB_ICONINFORMATION);
}

/* ---------- Toolset UI ---------- */
#define ID_OVERLAY_OPEN 120
#define ID_OVERLAY_CLOSE 121
#define ID_MINIMIZE 123
#define ID_CLOSE 124
#define ID_STEAM 125
#define ID_F10_TOGGLE 127
#define ID_F10STATE 128
static std::wstring OverlayExe(){return Join(gExeDir,L"ControllerOverlay\\WXXControllerOverlay.exe");}
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
    const wchar_t* parameters=open?nullptr:L"--close";
    auto result=ShellExecuteW(nullptr,L"open",exe.c_str(),parameters,gExeDir.c_str(),SW_SHOWNORMAL);
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
static void RefreshAll(){LoadState();InitializeOriginal();RefreshProfiles();RefreshSaveState();RefreshModState();RefreshF10State();}
static LRESULT CALLBACK Proc(HWND w,UINT msg,WPARAM wp,LPARAM lp);
/* 滚动容器：只画三张卡片、收滚动消息，控件通知一律转给主窗口处理。 */
static void ScrollContent(int pos){
    if(!gScrollBox)return;
    SCROLLINFO si{};si.cbSize=sizeof si;si.fMask=SIF_ALL;GetScrollInfo(gScrollBox,SB_VERT,&si);
    int maxPos=int(si.nMax)-int(si.nPage)+1;if(maxPos<0)maxPos=0;
    if(pos<0)pos=0;if(pos>maxPos)pos=maxPos;
    if(pos==si.nPos)return;
    ScrollWindowEx(gScrollBox,0,si.nPos-pos,nullptr,nullptr,nullptr,nullptr,SW_INVALIDATE|SW_ERASE|SW_SCROLLCHILDREN);
    si.fMask=SIF_POS;si.nPos=pos;SetScrollInfo(gScrollBox,SB_VERT,&si,TRUE);
}
static LRESULT CALLBACK ScrollProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
    switch(msg){
    case WM_ERASEBKGND:return 1;
    case WM_PAINT:{
        PAINTSTRUCT ps;HDC dc=BeginPaint(w,&ps);RECT r;GetClientRect(w,&r);FillRect(dc,&r,gBackground);
        SCROLLINFO si{};si.cbSize=sizeof si;si.fMask=SIF_POS;GetScrollInfo(w,SB_VERT,&si);
        /* 卡片坐标要减掉容器在窗口里的偏移 kScrollTop，再减滚动量。 */
        const int oy=-si.nPos-kScrollTop;
        HPEN pen=CreatePen(PS_SOLID,1,RGB(77,46,55));auto oldPen=SelectObject(dc,pen);auto oldBrush=SelectObject(dc,gCard);
        RoundRect(dc,24,88+oy,750,216+oy,16,16);RoundRect(dc,24,226+oy,750,310+oy,16,16);
        RoundRect(dc,24,320+oy,750,440+oy,16,16);RoundRect(dc,24,450+oy,750,534+oy,16,16);
        Label(dc,48,96+oy,L"六槽武器",RGB(232,220,207),gTitleFont);
        Label(dc,48,234+oy,L"控制器覆层",RGB(232,220,207),gTitleFont);
        Label(dc,48,328+oy,L"存档切换",RGB(232,220,207),gTitleFont);
        Label(dc,48,458+oy,L"F10 存档",RGB(232,220,207),gTitleFont);
        SelectObject(dc,oldPen);SelectObject(dc,oldBrush);DeleteObject(pen);EndPaint(w,&ps);return 0;
    }
    case WM_VSCROLL:{
        SCROLLINFO si{};si.cbSize=sizeof si;si.fMask=SIF_ALL;GetScrollInfo(w,SB_VERT,&si);
        int pos=si.nPos;
        switch(LOWORD(wp)){
        case SB_LINEUP:pos-=28;break;
        case SB_LINEDOWN:pos+=28;break;
        case SB_PAGEUP:pos-=int(si.nPage);break;
        case SB_PAGEDOWN:pos+=int(si.nPage);break;
        case SB_THUMBTRACK:case SB_THUMBPOSITION:pos=si.nTrackPos;break;
        case SB_TOP:pos=0;break;
        case SB_BOTTOM:pos=int(si.nMax);break;
        default:return 0;
        }
        ScrollContent(pos);return 0;
    }
    case WM_MOUSEWHEEL:{
        SCROLLINFO si{};si.cbSize=sizeof si;si.fMask=SIF_POS;GetScrollInfo(w,SB_VERT,&si);
        ScrollContent(si.nPos-(GET_WHEEL_DELTA_WPARAM(wp)/WHEEL_DELTA)*64);return 0;
    }
    case WM_DRAWITEM:case WM_MEASUREITEM:case WM_COMMAND:
    case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:case WM_CTLCOLORLISTBOX:
        return Proc(gMain,msg,wp,lp);
    }
    return DefWindowProcW(w,msg,wp,lp);
}
static LRESULT CALLBACK Proc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
    switch(msg){
    case WM_CREATE:{
        gMain=w;
        gFont=CreateFontW(-16,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        gTitleFont=CreateFontW(-24,0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        Add(w,L"BUTTON",L"启动忍龙4",0,500,18,152,34,ID_STEAM);
        Add(w,L"BUTTON",L"—",0,670,18,38,32,ID_MINIMIZE);
        Add(w,L"BUTTON",L"×",0,716,18,38,32,ID_CLOSE);
        /* 内容区：子窗口 + 纵向滚动条。控件坐标 = 绝对 y - kScrollTop。 */
        WNDCLASSW sc{};sc.hInstance=GetModuleHandleW(nullptr);sc.lpfnWndProc=ScrollProc;sc.lpszClassName=L"WXXToolsetScroll";sc.hCursor=LoadCursorW(nullptr,IDC_ARROW);sc.hbrBackground=gBackground;RegisterClassW(&sc);
        gScrollBox=CreateWindowExW(0,L"WXXToolsetScroll",L"",WS_CHILD|WS_VISIBLE|WS_VSCROLL|WS_CLIPCHILDREN,0,kScrollTop,774,570-kScrollTop,w,nullptr,GetModuleHandleW(nullptr),nullptr);
        HWND c=gScrollBox;
        gModState=Add(c,L"STATIC",L"",0,48,138-kScrollTop,420,24,ID_MODSTATE);
        Add(c,L"BUTTON",L"六槽武器：关闭",0,600,96-kScrollTop,126,36,ID_MOD_LOAD);
        Add(c,L"BUTTON",L"6槽武器设置",0,48,168-kScrollTop,180,38,ID_CONFIG);
        gOverlayState=Add(c,L"STATIC",L"未打开",0,48,276-kScrollTop,420,24,130);
        Add(c,L"BUTTON",L"打开",0,600,234-kScrollTop,126,36,ID_OVERLAY_OPEN);
        gSaveState=Add(c,L"STATIC",L"",0,48,366-kScrollTop,440,24,ID_SAVESTATE);
        gProfileBox=Add(c,L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,48,396-kScrollTop,440,150,ID_PROFILE);
        SendMessageW(gProfileBox,CB_SETITEMHEIGHT,static_cast<WPARAM>(-1),30);
        Add(c,L"BUTTON",L"切换存档",0,506,392-kScrollTop,110,38,ID_SWITCH);
        Add(c,L"BUTTON",L"存档目录",0,628,392-kScrollTop,98,38,ID_OPENSAVES+100);
        gF10State=Add(c,L"STATIC",L"",0,48,500-kScrollTop,500,24,ID_F10STATE);
        Add(c,L"BUTTON",L"F10 存档：开启",0,600,458-kScrollTop,126,36,ID_F10_TOGGLE);
        Add(c,L"BUTTON",L"查看日志",0,462,458-kScrollTop,126,36,ID_OPENSAVES);
        /* 内容高度 = 最下面那个控件的底 + 余量；超过视口高度才出现滚动条。 */
        int contentBottom=0;
        for(HWND child=GetWindow(gScrollBox,GW_CHILD);child;child=GetWindow(child,GW_HWNDNEXT)){
            /* 下拉框的窗口高度含弹出列表，不算进内容高度。 */
            if(GetDlgCtrlID(child)==ID_PROFILE)continue;
            RECT rc{};GetWindowRect(child,&rc);
            POINT tl{rc.left,rc.bottom};ScreenToClient(gScrollBox,&tl);
            if(tl.y>contentBottom)contentBottom=tl.y;
        }
        SCROLLINFO si{};si.cbSize=sizeof si;si.fMask=SIF_RANGE|SIF_PAGE|SIF_POS;
        si.nMin=0;si.nMax=contentBottom+16;si.nPage=UINT(570-kScrollTop);si.nPos=0;
        SetScrollInfo(gScrollBox,SB_VERT,&si,TRUE);
        SetText(Ctl(ID_MOD_LOAD),gWeaponOn?L"六槽武器：开启":L"六槽武器：关闭");
        SetText(Ctl(ID_F10_TOGGLE),gF10On?L"F10 存档：开启":L"F10 存档：关闭");
        RefreshAll();
        /* 打开面板时游戏里已经注入着：以实际状态为准记下来，别把玩家的 Mod 关掉。 */
        if(gModLoaded&&gModEnabled&&!gWeaponOn){
            gWeaponOn=true;WritePrivateProfileStringW(L"Toolset",L"WeaponSwitch",L"1",IniPath().c_str());
            SetText(Ctl(ID_MOD_LOAD),L"六槽武器：开启");
            Log(L"游戏里 Mod 已启用，六槽武器开关按实际状态记为开启");
        }
        SetTimer(w,1,1000,nullptr);return 0;
    }
    case WM_NCHITTEST:{
        LRESULT hit=DefWindowProcW(w,msg,wp,lp);POINT p{GET_X_LPARAM(lp),GET_Y_LPARAM(lp)};ScreenToClient(w,&p);
        HWND child=ChildWindowFromPointEx(w,p,CWP_SKIPINVISIBLE|CWP_SKIPDISABLED);
        if(hit==HTCLIENT&&p.y<76&&child==w)return HTCAPTION;return hit;
    }
    /* 滚轮统一交给滚动容器处理：控件不处理的滚轮也会冒泡到这里。 */
    case WM_MOUSEWHEEL:
        if(gScrollBox)return SendMessageW(gScrollBox,WM_MOUSEWHEEL,wp,lp);
        break;
    case WM_ERASEBKGND:return 1;
    case WM_PAINT:{
        PAINTSTRUCT ps;HDC dc=BeginPaint(w,&ps);RECT r;GetClientRect(w,&r);FillRect(dc,&r,gBackground);
        DrawIconEx(dc,30,19,LoadIconW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(1)),48,48,0,nullptr,DI_NORMAL);
        Label(dc,94,20,L"WXX NINJA GAIDEN 4",RGB(236,68,84),gTitleFont);
        Label(dc,96,52,L"TOOLSET",RGB(179,155,115),gFont);
        EndPaint(w,&ps);return 0;
    }
    case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:case WM_CTLCOLORLISTBOX:{
        HDC dc=reinterpret_cast<HDC>(wp);SetTextColor(dc,RGB(188,177,177));SetBkColor(dc,RGB(26,26,33));return reinterpret_cast<LRESULT>(gCard);
    }
    case WM_DRAWITEM:{
        auto d=reinterpret_cast<DRAWITEMSTRUCT*>(lp);if(d->CtlType!=ODT_BUTTON)break;
        bool down=(d->itemState&ODS_SELECTED)!=0,disabled=(d->itemState&ODS_DISABLED)!=0;
        FillRect(d->hDC,&d->rcItem,(d->CtlID==ID_STEAM||d->CtlID==ID_MINIMIZE||d->CtlID==ID_CLOSE||d->CtlID==ID_OPENSAVES)?gBackground:gCard);
        if(d->CtlID==ID_MINIMIZE||d->CtlID==ID_CLOSE){
            if(down){HBRUSH pressed=CreateSolidBrush(d->CtlID==ID_CLOSE?RGB(133,37,54):RGB(47,43,51));FillRect(d->hDC,&d->rcItem,pressed);DeleteObject(pressed);}
            Gdiplus::Graphics graphics(d->hDC);graphics.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
            Gdiplus::Pen line(Gdiplus::Color(255,206,192,193),1.5f);
            float cx=(d->rcItem.right+d->rcItem.left)*0.5f,cy=(d->rcItem.top+d->rcItem.bottom)*0.5f;
            if(d->CtlID==ID_MINIMIZE)graphics.DrawLine(&line,cx-6,cy+2,cx+6,cy+2);
            else{graphics.DrawLine(&line,cx-5,cy-5,cx+5,cy+5);graphics.DrawLine(&line,cx+5,cy-5,cx-5,cy+5);}
            if(d->itemState&ODS_FOCUS)DrawFocusRect(d->hDC,&d->rcItem);return TRUE;
        }
        if(d->CtlID==ID_MOD_LOAD||d->CtlID==ID_F10_TOGGLE){
            const bool on=d->CtlID==ID_MOD_LOAD?gWeaponOn:gF10On;
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
        HBRUSH brush=CreateSolidBrush(down?RGB(100,35,49):RGB(37,32,40));HPEN pen=CreatePen(PS_SOLID,1,RGB(99,51,63));
        auto ob=SelectObject(d->hDC,brush);auto op=SelectObject(d->hDC,pen);RoundRect(d->hDC,d->rcItem.left,d->rcItem.top,d->rcItem.right,d->rcItem.bottom,8,8);
        wchar_t t[128];GetWindowTextW(d->hwndItem,t,128);SetTextColor(d->hDC,disabled?RGB(100,94,98):RGB(226,211,195));SetBkMode(d->hDC,TRANSPARENT);SelectObject(d->hDC,gFont);DrawTextW(d->hDC,t,-1,&d->rcItem,DT_CENTER|DT_VCENTER|DT_SINGLELINE);
        if(d->itemState&ODS_FOCUS){RECT f=d->rcItem;InflateRect(&f,-4,-4);DrawFocusRect(d->hDC,&f);}
        SelectObject(d->hDC,ob);SelectObject(d->hDC,op);DeleteObject(brush);DeleteObject(pen);return TRUE;
    }
    case WM_TIMER:{
        const DWORD pid=FindGame();
        bool running=pid!=0;RefreshModState();RefreshF10State();
        if(!running&&gCurrentProfile.empty()){InitializeOriginal();RefreshProfiles();RefreshSaveState();}
        /* 开关记的是意图：游戏一起就把状态变成现实——没注入就主动注入，注入了就把武器键切到开关的位置。 */
        if(!running)gAutoInjectPid=0;
        else if(!gModLoaded&&(gWeaponOn||gF10On)){
            if(gAutoInjectPid!=pid){gAutoInjectPid=pid;DoInject(true);}
        }else if(gModLoaded&&gModEnabled!=gWeaponOn)SendModSwitch(pid,gWeaponOn);
        /* 开关也可能被 ini 直接改（手改配置），跟着同步，避免面板显示与实际相反。 */
        const bool f10FromIni=GetPrivateProfileIntW(L"Save",L"TestKey",121,IniPath().c_str())!=0;
        if(f10FromIni!=gF10On){
            gF10On=f10FromIni;
            SetText(Ctl(ID_F10_TOGGLE),gF10On?L"F10 存档：开启":L"F10 存档：关闭");
        }
        const bool weaponFromIni=GetPrivateProfileIntW(L"Toolset",L"WeaponSwitch",0,IniPath().c_str())!=0;
        if(weaponFromIni!=gWeaponOn){
            gWeaponOn=weaponFromIni;
            SetText(Ctl(ID_MOD_LOAD),gWeaponOn?L"六槽武器：开启":L"六槽武器：关闭");
        }
        gOverlayOn=OverlayPid()!=0;
        if(gOverlayPending&&(gOverlayOn||GetTickCount64()>gOverlayPending)){
            gOverlayPending=0;EnableWindow(Ctl(ID_OVERLAY_OPEN),TRUE);
        }
        SetText(gOverlayState,gOverlayPending?L"正在打开…":(gOverlayOn?L"运行中 · 手柄输入与震动捕获":L"未打开"));
        return 0;
    }
    case WM_COMMAND:
        switch(LOWORD(wp)){
        case ID_PROFILE:if(HIWORD(wp)==CBN_DROPDOWN){LoadState();RefreshProfiles();RefreshSaveState();}return 0;
        case ID_MOD_LOAD:
            gWeaponOn=!gWeaponOn;
            WritePrivateProfileStringW(L"Toolset",L"WeaponSwitch",gWeaponOn?L"1":L"0",IniPath().c_str());
            SetText(Ctl(ID_MOD_LOAD),gWeaponOn?L"六槽武器：开启":L"六槽武器：关闭");
            if(FindGame()){if(gWeaponOn)DoInject();else DoStop();}
            else Log(L"六槽武器开关＝%s：游戏没在运行，已记下状态，启动后自动注入",gWeaponOn?L"开":L"关");
            RefreshModState();return 0;
        case ID_MOD_STOP:DoStop();RefreshModState();return 0;
        case ID_CONFIG:ShellExecuteW(w,L"open",Join(gExeDir,L"SixSlotConfig.exe").c_str(),nullptr,gExeDir.c_str(),SW_SHOWNORMAL);return 0;
        case ID_OVERLAY_OPEN:
            if(OverlayPid()){Log(L"覆层已经在运行，不再重复启动");return 0;}
            Overlay(true);gOverlayPending=GetTickCount64()+5000;EnableWindow(Ctl(ID_OVERLAY_OPEN),FALSE);return 0;
        case ID_OVERLAY_CLOSE:Overlay(false);return 0;
        case ID_SWITCH:SwitchToProfile();return 0;
        case ID_F10_TOGGLE:
            gF10On=!gF10On;
            WritePrivateProfileStringW(L"Save",L"TestKey",gF10On?L"121":L"0",IniPath().c_str());
            SetText(Ctl(ID_F10_TOGGLE),gF10On?L"F10 存档：开启":L"F10 存档：关闭");
            Log(L"F10 主动存档＝%s（写在 SixSlot.ini 的 [Save] TestKey，mod 一秒内热重载）",gF10On?L"开":L"关");
            return 0;
        case ID_OPENSAVES+100:ShellExecuteW(w,L"open",gSavesRoot.c_str(),nullptr,nullptr,SW_SHOWNORMAL);return 0;
        case ID_OPENSAVES:ShellExecuteW(w,L"open",gLogFile.c_str(),nullptr,gExeDir.c_str(),SW_SHOWNORMAL);return 0;
        case ID_STEAM:{
            auto result=ShellExecuteW(w,L"open",L"steam://rungameid/2627260",nullptr,nullptr,SW_SHOWNORMAL);
            if(reinterpret_cast<INT_PTR>(result)<=32)Say(L"启动忍龙4",L"无法打开 Steam，请先运行 Steam 客户端。",MB_OK|MB_ICONERROR);
            return 0;
        }
        case ID_MINIMIZE:ShowWindow(w,SW_MINIMIZE);return 0;
        case ID_CLOSE:DestroyWindow(w);return 0;
        }return 0;
    case WM_DESTROY:DeleteObject(gFont);DeleteObject(gTitleFont);PostQuitMessage(0);return 0;
    }return DefWindowProcW(w,msg,wp,lp);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR cmdline,int show){
    Gdiplus::GdiplusStartupInput gdiplusInput;ULONG_PTR gdiplusToken;Gdiplus::GdiplusStartup(&gdiplusToken,&gdiplusInput,nullptr);
    SetProcessDPIAware();gExeDir=SelfDir();gSavesRoot=Join(gExeDir,L"saves");gSaveDir=LocalSaveDir();
    gStateFile=Join(gSavesRoot,L"current.txt");gLogFile=Join(gExeDir,L"WXXToolset.log");
    gWeaponOn=GetPrivateProfileIntW(L"Toolset",L"WeaponSwitch",0,IniPath().c_str())!=0;
    gF10On=GetPrivateProfileIntW(L"Save",L"TestKey",121,IniPath().c_str())!=0;
    gIntegrityLevel=SelfIntegrityLevel();
    gLowIntegrity=gIntegrityLevel==0;
    gHighIntegrity=gIntegrityLevel>=2;
    Log(L"面板启动：%s",gLowIntegrity?L"低完整性（无法访问游戏；运行 Repair-Permissions.cmd 修复 EXE 标签后重启）":
        (gHighIntegrity?L"高完整性（管理员）":L"中完整性（正常）"));
    std::wstring args=cmdline?cmdline:L"";
    if(args==L"--stop"){DoStop();return 0;}
    if(args==L"--overlay-open"){Overlay(true);return 0;}
    if(args==L"--overlay-close"){Overlay(false);return 0;}
    HWND existing=FindWindowW(L"WXXNinjaGuiden4ToolSet",nullptr);if(existing){ShowWindow(existing,SW_RESTORE);SetForegroundWindow(existing);return 0;}
    WNDCLASSW wc{};wc.hInstance=instance;wc.lpfnWndProc=Proc;wc.lpszClassName=L"WXXNinjaGuiden4ToolSet";wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);wc.hbrBackground=gBackground;wc.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(1));RegisterClassW(&wc);
    DWORD style=WS_POPUP|WS_MINIMIZEBOX|WS_SYSMENU;RECT work;SystemParametersInfoW(SPI_GETWORKAREA,0,&work,0);
    HWND w=CreateWindowW(wc.lpszClassName,L"WXXNinjaGuiden4ToolSet",style,work.left+(work.right-work.left-774)/2,work.top+(work.bottom-work.top-570)/2,774,570,nullptr,nullptr,instance,nullptr);
    int corner=2;DwmSetWindowAttribute(w,33,&corner,sizeof corner);
    ShowWindow(w,show);MSG msg{};while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(w,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}return 0;
}
