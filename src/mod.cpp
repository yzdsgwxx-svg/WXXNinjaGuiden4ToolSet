#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <initializer_list>
#include "MinHook.h"

// Steam build checked against both disk image and live instruction bytes.
// Weapon IDs: 0 twin blades, 1 staff, 2 lance, 3 assassin tools,
// 4 dark dragon blade, 5 Ryu dragon sword, 6 Yakumo DLC scythe, 7 Ryu DLC.
static HMODULE self;
static uintptr_t base;
static wchar_t configPath[MAX_PATH], logPath[MAX_PATH];
static SRWLOCK logLock=SRWLOCK_INIT;
static std::atomic<bool> enabled{true};
static std::atomic<ULONGLONG> request{0};
static std::atomic<int> weapon5{4},weapon6{6};
// Trigger keys are Windows virtual-key codes from the [Keys] section; Q and E by default.
static std::atomic<int> vk5{'Q'},vk6{'E'};
static std::atomic<unsigned> updates{0};
static std::atomic<uintptr_t> lastPlayer{0};
static std::atomic<int> currentWeapon{-1};
/* 主动存档：只有一个入口——按 [Save] TestKey（默认 F10）。没有退出时存档、没有菜单自动存。 */
static std::atomic<int> lastSaveAt{0},vkSaveTest{0};
static std::atomic<int> vkKickMode{5};
static std::atomic<int> saveInFlight{0};   // 1 = 我们踢出去的存档阶段还没走完
static std::atomic<int> saveSeqStage{0};    // 0=空闲；3=阶段3 已踢；5=阶段5 已踢
static std::atomic<int> saveStageSeen{0};        // 1 = 本次阶段真的跑起来过（非空闲）
static std::atomic<ULONGLONG> saveStageSetAt{0}; // 我们写下这个阶段的时刻
static std::atomic<int> probeVerbose{1};  // [Save] Probe：1=诊断日志全开
static std::atomic<ULONGLONG> saveWaitDone{0};    // 上一次等存档结束的时刻（避免连环等）
static std::atomic<ULONGLONG> lastSkipLog{0};    // 去重日志限流
static std::atomic<ULONGLONG> kickRequest{0};
static void KickGameSave(const char* reason);
static void WaitForPendingSave(const char* where);
static bool ValidSession(uintptr_t session);
static uintptr_t ManagerFromSession(uintptr_t session);
using Update=void(__fastcall*)(void*);
using Select=bool(__fastcall*)(void*,int);
using Resolve=int(__fastcall*)(void*,bool,int,bool);
using Unlocked=bool(__fastcall*)(void*,int);
static Update updateOriginal;
static Select selectOriginal;
static Resolve resolveOriginal;
struct Context {int weapon=-1; int key=0; void* player=nullptr; void* manager=nullptr; int page=-1; int slot=0; bool selected=false; bool resolved=false;};
static thread_local Context context;

static void NoteUpdateGap();
static void Log(const char* fmt,...) {
    AcquireSRWLockExclusive(&logLock);
    FILE* f=nullptr;
    /* 每 256 行查一次大小，超过 4 MB 就轮转一份：诊断日志不能把磁盘写满。 */
    static unsigned lines=0;
    if(++lines%256==0){
        WIN32_FILE_ATTRIBUTE_DATA attr{};
        if(GetFileAttributesExW(logPath,GetFileExInfoStandard,&attr)){
            const unsigned long long size=(static_cast<unsigned long long>(attr.nFileSizeHigh)<<32)|attr.nFileSizeLow;
            if(size>4ull*1024*1024){
                wchar_t rotated[MAX_PATH];swprintf_s(rotated,L"%s.1",logPath);
                MoveFileExW(logPath,rotated,MOVEFILE_REPLACE_EXISTING);
            }
        }
    }
    if(_wfopen_s(&f,logPath,L"ab")==0 && f){
        SYSTEMTIME t;GetLocalTime(&t);
        fprintf(f,"%02d:%02d:%02d.%03d ",t.wHour,t.wMinute,t.wSecond,t.wMilliseconds);
        va_list a;va_start(a,fmt);vfprintf(f,fmt,a);va_end(a);
        fputc('\n',f);fclose(f);
    }
    ReleaseSRWLockExclusive(&logLock);
}
static bool validWeapon(int n){return n==0||n==1||n==2||n==3||n==4||n==6;}
// Weapon manager state, see SelectHook target 0xcbf680: byte +0x218 = page, dword +0x21c = slot.
// Slots are the native direction codes used by update 0x608730: 13 up, 15 right, 14 down, 16 left.
static constexpr uintptr_t kManagerPage=0x218,kManagerSlot=0x21c;
static constexpr int kNativeSlots[]={13,15,14,16};
// Find the native (page,slot) that resolves to this weapon, so manager state can be kept in sync.
static bool LocateNativeSlot(void* manager,int weapon,int& page,int& slot){
    if(!resolveOriginal)return false;
    for(int p=0;p<2;++p){
        for(int s:kNativeSlots){
            if(resolveOriginal(manager,p!=0,s,true)==weapon){page=p;slot=s;return true;}
        }
    }
    return false;
}
static void ApplyNativeSlot(void* manager,int page,int slot){
    *reinterpret_cast<unsigned char*>(uintptr_t(manager)+kManagerPage)=static_cast<unsigned char>(page?1:0);
    *reinterpret_cast<int*>(uintptr_t(manager)+kManagerSlot)=slot;
}
// Both hooks are installed on the shared helpers, so filter by the call sites inside update 0x608730.
static bool IsWeaponSelectCall(uintptr_t ret){
    return ret==base+0x608914||ret==base+0x60895d||ret==base+0x6089a9||ret==base+0x6089f2;
}
static bool IsWeaponResolveCall(uintptr_t ret){
    return ret==base+0x60892e||ret==base+0x608977||ret==base+0x6089c3||ret==base+0x608a0c;
}
static bool validKey(int vk){return vk>0&&vk<0x100;}
static void LoadConfig(){
    int a=GetPrivateProfileIntW(L"Weapons",L"Key5",4,configPath);
    int b=GetPrivateProfileIntW(L"Weapons",L"Key6",6,configPath);
    if(!validWeapon(a)){Log("Invalid Key5=%d; disabled this binding",a);a=-1;}
    if(!validWeapon(b)){Log("Invalid Key6=%d; disabled this binding",b);b=-1;}
    weapon5=a;weapon6=b;
    int k5=GetPrivateProfileIntW(L"Keys",L"Key5",'Q',configPath);
    int k6=GetPrivateProfileIntW(L"Keys",L"Key6",'E',configPath);
    if(!validKey(k5)){Log("Invalid key code %d for slot 5; falling back to Q",k5);k5='Q';}
    if(!validKey(k6)){Log("Invalid key code %d for slot 6; falling back to E",k6);k6='E';}
    // A shared key would make the two slots fight over one press; keep slot 5 only.
    if(k5==k6){Log("Both slots mapped to key code %d; slot 6 disabled until reassigned",k5);k6=0;}
    vk5=k5;vk6=k6;
    /* 主动存档：[Save] TestKey 手动触发键（默认 F10，0 = 关闭）。这是唯一的写盘入口。 */
    int testKey=GetPrivateProfileIntW(L"Save",L"TestKey",VK_F10,configPath);
    if(!validKey(testKey))testKey=0;
    vkSaveTest=testKey;
    int kickMode=GetPrivateProfileIntW(L"Save",L"KickMode",5,configPath);
    if(kickMode<1||kickMode>6)kickMode=5;
    vkKickMode=kickMode;
    probeVerbose=GetPrivateProfileIntW(L"Save",L"Probe",1,configPath)?1:0;
    Log("Configuration loaded: slot5 weapon %d on key 0x%02x; slot6 weapon %d on key 0x%02x",a,k5,b,k6);
    if(testKey)Log("Manual save key: 0x%02x (manual only; no exit-save, no menu auto-save)",testKey);
    else Log("Manual save key: off (no save writes at all)");
    Log("Diagnostics: probe=%s kick mode=%d",probeVerbose.load()?"on":"off",kickMode);
}
static bool __fastcall SelectHook(void* manager,int direction){    if(IsWeaponSelectCall(uintptr_t(_ReturnAddress()))){
        if(context.weapon>=0){
            context.selected=true;
            // Keep the original four-slot assignments and selected page untouched.
            return false;
        }
        // Native slot key (keyboard 1..4 / the same action codes). Only interferes while the Mod is
        // enabled: disabled means the original selector (including paging) works untouched.
        if(enabled.load(std::memory_order_relaxed)){
            auto* page=reinterpret_cast<unsigned char*>(uintptr_t(manager)+kManagerPage);
            auto* slot=reinterpret_cast<int*>(uintptr_t(manager)+kManagerSlot);
            if(*page || *slot==direction){
                Log("Native slot key %d: selector pinned to page 0 (was page %d slot %d)",direction,int(*page),*slot);
                *page=0;
                if(*slot==direction)*slot=0;
            }
        }
    }
    return selectOriginal(manager,direction);
}
static int __fastcall ResolveHook(void* manager,bool page,int direction,bool check){
    if(IsWeaponResolveCall(uintptr_t(_ReturnAddress())) && context.weapon>=0 && context.selected){
        const int desired=context.weapon;
        const int previous=*reinterpret_cast<int*>(uintptr_t(context.player)+0x8054);
        if(!reinterpret_cast<Unlocked>(base+0xcc04a0)(manager,desired)){
            Log("Slot %d rejected: weapon %d is not unlocked",context.key,desired);
            context.resolved=true;
            return previous;
        }
        // The native select call is skipped on purpose, which leaves manager page/slot at their old
        // values. That made a later native key press (slot already equal) fall into the paging branch
        // and jump to the other page. Sync manager to where this weapon really lives.
        int nativePage=-1,nativeSlot=0;
        if(LocateNativeSlot(manager,desired,nativePage,nativeSlot)){
            context.manager=manager;context.page=nativePage;context.slot=nativeSlot;
            ApplyNativeSlot(manager,nativePage,nativeSlot);
            Log("Slot %d: manager synced to page %d slot %d for weapon %d",context.key,nativePage,nativeSlot,desired);
        }else{
            Log("Slot %d: weapon %d not found in the native slot table; manager state left unchanged",context.key,desired);
        }
        context.resolved=true;
        Log("Slot %d: native switch requested %d -> %d",context.key,previous,desired);
        return desired;
    }
    return resolveOriginal(manager,page,direction,check);
}
static void __fastcall UpdateHook(void* player){
    ++updates;
    NoteUpdateGap();
    /* F10 主动存档：请求在 Worker 里置位，这里在游戏线程踢一脚（正常游玩时这条路最先到）。
       人在菜单里时玩家 update 停了，这条路走不到，由 Worker 兜底。 */
    if(const ULONGLONG ticked=kickRequest.exchange(0)){
        if(GetTickCount64()-ticked<1500)KickGameSave("manual save key");
    }
    lastPlayer=reinterpret_cast<uintptr_t>(player);
    currentWeapon=*reinterpret_cast<int*>(uintptr_t(player)+0x8054);
    // Nested/reentrant callbacks must not consume or overwrite the outer context.
    if(context.player || !enabled.load(std::memory_order_relaxed)){
        updateOriginal(player);return;
    }
    const auto packed=request.exchange(0);
    if(!packed){updateOriginal(player);return;}
    const auto issued=packed>>8;
    const int key=int(packed&0xff);
    if(GetTickCount64()-issued>200){updateOriginal(player);return;}
    const auto entity=*reinterpret_cast<uintptr_t*>(uintptr_t(player)+0xb10);
    if(!entity || *reinterpret_cast<int*>(entity+0x600)==2){
        Log("Slot %d ignored: first version supports Yakumo only",key);
        updateOriginal(player);return;
    }
    int desired=(key==5?weapon5.load():weapon6.load());
    if(!validWeapon(desired)){updateOriginal(player);return;}
    context={desired,key,player,nullptr,-1,0,false,false};
    // Supply one frame of the existing up-direction input. The native input
    // routine still checks menus, locks and player state before returning it.
    auto input=reinterpret_cast<unsigned char*>(uintptr_t(player)+0xbd0+0x41b+13);
    const auto saved=*input;
    *input=1;
    updateOriginal(player);
    *input=saved;
    // The native update resolves again further down; re-apply so the final state matches the weapon.
    if(context.resolved && context.manager && context.page>=0)ApplyNativeSlot(context.manager,context.page,context.slot);
    if(!context.resolved)Log("Slot %d not consumed: native switch gate blocked this frame",key);
    currentWeapon=*reinterpret_cast<int*>(uintptr_t(player)+0x8054);
    if(context.resolved && context.manager)Log("Slot %d done: weapon=%d manager page=%d slot=%d",key,currentWeapon.load(),
        int(*reinterpret_cast<unsigned char*>(uintptr_t(context.manager)+kManagerPage)),
        *reinterpret_cast<int*>(uintptr_t(context.manager)+kManagerSlot));
    context={};
}
static bool Match(uintptr_t rva,const unsigned char* bytes,size_t n){
    if(memcmp(reinterpret_cast<void*>(base+rva),bytes,n)==0)return true;
    Log("Unsupported/modified game instructions at RVA %llx; no hooks installed",(unsigned long long)rva);
    return false;
}
/* ================= 存档探针：只记录，不调用任何游戏函数 =================
   采集四件事：(1) saveSlotData 的高层调用者（返回地址）、(2) 回标题/退出游戏时
   游戏自己是否写盘、(3) 存档管理器实例是否跨标题界面存活、(4) 每次写盘的真实时间。
   规则：hook 一律原样转发（不改参数、不跳过）；读实例一律 SEH 保护；每帧路径不写日志。
   存档管理器：0x1026790 new 出 0xae8 字节，首 qword = vtable base+0x2262d10。
   请求码 -> 文件：6 = SystemData.vdf，7 = GameData.dat，8 = SlotData_{n}.dat。 */
static constexpr uintptr_t kVtableSaveManager=0x2262d10;
static constexpr uintptr_t kOffBusy=0x55a,kOffRequest=0x55c,kOffSlot=0x568;
static std::atomic<uintptr_t> saveManager{0};
static std::atomic<int> saveManagerSource{0}; // 1 = 内存扫描，2 = 构造 hook，3 = load 请求 hook
using RequestNoArgs=bool(__fastcall*)(void*);
using RequestSlot=bool(__fastcall*)(void*,int,const void*);
using ManagerCtor=void*(__fastcall*)(void*);
using ManagerDtor=void*(__fastcall*)(void*,int);
static RequestNoArgs request7Original,request6Original;
static RequestSlot request8Original;
static ManagerCtor ctorOriginal;
static ManagerDtor dtorOriginal;
static uintptr_t CallerRva(){return uintptr_t(_ReturnAddress())-base;}
static void LogManagerState(const char* tag,void* manager,uintptr_t caller,bool accepted){
    unsigned char busy=0;unsigned code=0,slot=0;
    __try{
        busy=*reinterpret_cast<unsigned char*>(uintptr_t(manager)+kOffBusy);
        code=*reinterpret_cast<unsigned*>(uintptr_t(manager)+kOffRequest);
        slot=*reinterpret_cast<unsigned*>(uintptr_t(manager)+kOffSlot);
    }__except(EXCEPTION_EXECUTE_HANDLER){Log("PROBE %s this=%p unreadable",tag,manager);return;}
    if(probeVerbose.load())Log("PROBE %s this=%p caller=+0x%llx accepted=%d busy=%u code=%u slot=%u",tag,manager,
        (unsigned long long)caller,int(accepted),unsigned(busy),code,slot);
}
static void DumpBytes(const char* tag,const void* p,size_t n){
    if(!p)return;
    char line[3*64+1];size_t w=0;
    __try{
        const unsigned char* b=static_cast<const unsigned char*>(p);
        for(size_t i=0;i<n&&w+3<sizeof line;++i)w+=sprintf_s(line+w,sizeof line-w,"%02x",b[i]);
    }__except(EXCEPTION_EXECUTE_HANDLER){Log("PROBE %s at %p unreadable",tag,p);return;}
    line[w]=0;Log("PROBE %s %p = %s",tag,p,line);
}
static bool __fastcall Request7Hook(void* manager){
    const uintptr_t caller=CallerRva();
    const bool ok=request7Original(manager);
    LogManagerState("SAVE GameData",manager,caller,ok);
    return ok;
}
static bool __fastcall Request6Hook(void* manager){
    const uintptr_t caller=CallerRva();
    const bool ok=request6Original(manager);
    LogManagerState("SAVE System",manager,caller,ok);
    return ok;
}
static bool __fastcall Request8Hook(void* manager,int slot,const void* meta){
    const uintptr_t caller=CallerRva();
    const bool ok=request8Original(manager,slot,meta);
    unsigned char busy=0;unsigned code=0;
    __try{
        busy=*reinterpret_cast<unsigned char*>(uintptr_t(manager)+kOffBusy);
        code=*reinterpret_cast<unsigned*>(uintptr_t(manager)+kOffRequest);
    }__except(EXCEPTION_EXECUTE_HANDLER){busy=0;code=0;}
    if(probeVerbose.load())Log("PROBE SAVE Slot slot=%d meta=%p caller=+0x%llx accepted=%d busy=%u code=%u",slot,meta,
        (unsigned long long)caller,int(ok),unsigned(busy),code);
    DumpBytes("meta",meta,32);
    return ok;
}
static void* __fastcall ManagerCtorHook(void* manager){
    void* result=ctorOriginal(manager);
    const uintptr_t caller=CallerRva();
    saveManager=reinterpret_cast<uintptr_t>(result?result:manager);
    saveManagerSource=2;
    Log("PROBE manager ctor this=%p caller=+0x%llx",reinterpret_cast<void*>(saveManager.load()),(unsigned long long)caller);
    return result;
}
static void* __fastcall ManagerDtorHook(void* manager,int flags){
    const uintptr_t caller=CallerRva();
    WaitForPendingSave("manager dtor");
    if(saveManager.load()==reinterpret_cast<uintptr_t>(manager)){saveManager=0;saveManagerSource=0;}
    if(probeVerbose.load())Log("PROBE manager dtor this=%p flags=%d caller=+0x%llx",manager,flags,(unsigned long long)caller);
    return dtorOriginal(manager,flags);
}
/* 说明：实例**不靠内存扫描**拿。实测全地址空间扫一遍要 184 秒、还把游戏工作集顶上 5 GB，
   而且它只是在注入晚于管理器创建时才有用。现在改由 manager ctor hook + load/save 请求 hook
   提供实例（进关卡时必然有一次 load 请求），每次使用前仍按 vtable 校验。 */

struct WatchedFile{wchar_t name[64];ULONGLONG stamp;};
static WatchedFile watched[64];
static int watchedCount=0;
static void NoteFile(const wchar_t* name,ULONGLONG stamp,unsigned long long size){
    for(int i=0;i<watchedCount;++i){
        if(!_wcsicmp(watched[i].name,name)){
            if(watched[i].stamp&&watched[i].stamp!=stamp)Log("PROBE FILE %ls written size=%llu",name,size);
            watched[i].stamp=stamp;return;
        }
    }
    if(watchedCount<64){wcsncpy_s(watched[watchedCount].name,name,_TRUNCATE);watched[watchedCount].stamp=stamp;++watchedCount;}
}
static void WatchSaveFiles(){
    wchar_t dir[MAX_PATH]{};
    const DWORD n=GetEnvironmentVariableW(L"LOCALAPPDATA",dir,MAX_PATH);
    if(!n||n+32>=MAX_PATH)return;
    wcscat_s(dir,L"\\NINJAGAIDEN4");
    for(const wchar_t* name:{L"GameData.dat",L"SystemData.vdf"}){
        wchar_t path[MAX_PATH];swprintf_s(path,L"%s\\%ls",dir,name);
        WIN32_FILE_ATTRIBUTE_DATA a{};
        if(GetFileAttributesExW(path,GetFileExInfoStandard,&a))
            NoteFile(name,(ULONGLONG(a.ftLastWriteTime.dwHighDateTime)<<32)|a.ftLastWriteTime.dwLowDateTime,
                (static_cast<unsigned long long>(a.nFileSizeHigh)<<32)|a.nFileSizeLow);
    }
    wchar_t pattern[MAX_PATH];swprintf_s(pattern,L"%s\\SlotData_*.dat",dir);
    WIN32_FIND_DATAW fd{};HANDLE h=FindFirstFileW(pattern,&fd);
    if(h!=INVALID_HANDLE_VALUE){
        do{
            NoteFile(fd.cFileName,(ULONGLONG(fd.ftLastWriteTime.dwHighDateTime)<<32)|fd.ftLastWriteTime.dwLowDateTime,
                (static_cast<unsigned long long>(fd.nFileSizeHigh)<<32)|fd.nFileSizeLow);
        }while(FindNextFileW(h,&fd));
        FindClose(h);
    }
}
/* ================= 主动存档（F10）：踢游戏自己的存档状态机 =================
   教训（两轮闪退的真因）：0x102e3d0 / 0x102e510 这些"请求入口"的真实签名是
   (this, const Descriptor*)，进门第一步 `add rcx,0x580; call 0x102cba0` 是结构体拷贝
   （memcpy 0x7f+0x7f+0x3ff 字节 + 一个 dword），只传 this 会让它从垃圾 rdx 读，直接崩。
   **不要再自己拼 descriptor 调底层入口。**
   正确做法：0xc460b0 是游戏自己的存档状态机，参数 rcx = 会话对象（[session+0xe8] = 管理器），
   按 [session+0x100] 的状态 0..6 逐步存档；它由会话分发器按帧推进。
   我们只在游戏线程"踢一脚"（调用状态机入口），剩下交给游戏自己走完。 */
static constexpr uintptr_t kRvaSaveFlow=0xc460b0;
static constexpr uintptr_t kOffManagerHolder=0xe8,kOffFlowState=0x100;
static constexpr uintptr_t kOffSaveSlotIndex=0x568;   // manager+0x568 = 当前槽号
static constexpr uintptr_t kOffStageSlot=0xf4;        // session+0xf4 = 阶段参数（槽位）
static constexpr uintptr_t kOffStage=0xf0;            // session+0xf0 = 外层阶段（1=空闲，3=存档）
static constexpr unsigned kSaveStage=3;               // 阶段 3 = GameData+SystemData，之后自动串到 5（SlotData）
static constexpr unsigned kIdleStage=1;               // 阶段 1 = 空闲（请求队列处理完就回这里）
static constexpr unsigned kSaveSlotStage=5;           // 阶段 5 = SlotData_{n}.dat + GameData.dat
using SaveFlow=void(__fastcall*)(void*);
static SaveFlow saveFlowOriginal;
static std::atomic<uintptr_t> sessionObject{0};
static bool SessionAlive(){
    const uintptr_t s=sessionObject.load();
    if(!s)return false;
    uintptr_t holder=0,manager=0;
    __try{
        holder=*reinterpret_cast<const uintptr_t*>(s+kOffManagerHolder);
        if(holder)manager=*reinterpret_cast<const uintptr_t*>(holder);
    }__except(EXCEPTION_EXECUTE_HANDLER){return false;}
    return manager&&manager==saveManager.load();
}
static unsigned SessionStage(){
    const uintptr_t s=sessionObject.load();
    if(!s)return 0xffffffffu;
    unsigned stage=0xffffffffu;
    __try{stage=*reinterpret_cast<const unsigned*>(s+kOffStage);}
    __except(EXCEPTION_EXECUTE_HANDLER){stage=0xffffffffu;}
    return stage;
}
static unsigned SessionState(){
    const uintptr_t s=sessionObject.load();
    if(!s)return 0xffffffffu;
    unsigned state=0xffffffffu;
    __try{state=*reinterpret_cast<const unsigned*>(s+kOffFlowState);}
    __except(EXCEPTION_EXECUTE_HANDLER){state=0xffffffffu;}
    return state;
}
static void saveStepAbort(){lastSaveAt=0;}
/* 写"进入某阶段"的三个字段——游戏自己的 StartStage(0xc44790) 就是这么做的。 */
static bool SetSessionStage(uintptr_t session,unsigned stage,int slot){
    if(!session)return false;
    __try{
        *reinterpret_cast<unsigned*>(session+kOffStageSlot)=static_cast<unsigned>(slot);
        *reinterpret_cast<unsigned*>(session+kOffStage)=stage;
        *reinterpret_cast<unsigned*>(session+kOffFlowState)=0;
        return true;
    }__except(EXCEPTION_EXECUTE_HANDLER){Log("SAVE stage %u write faulted",stage);return false;}
}
static void KickGameSave(const char* reason){
    const uintptr_t session=sessionObject.load();
    if(!session){Log("SAVE skipped (%s): session not captured yet (enter a level first)",reason);return;}
    if(!ValidSession(session)){Log("SAVE skipped (%s): session invalid (or manager mismatch)",reason);return;}
    const uintptr_t manager=ManagerFromSession(session);
    if(manager&&saveManager.load()!=manager){
        saveManager=manager;saveManagerSource=4;
        Log("SAVE: instance taken from session chain: %p",reinterpret_cast<void*>(manager));
    }
    const unsigned stage=SessionStage();
    if(stage!=kIdleStage){Log("SAVE skipped (%s): stage %u busy (idle=%u)",reason,stage,kIdleStage);return;}
    const int now=int(GetTickCount64()/1000);
    const int previous=lastSaveAt.load();
    if(previous&&now-previous<2){
        const ULONGLONG stamp=GetTickCount64();
        if(stamp-lastSkipLog.load()>2000){lastSkipLog=stamp;Log("SAVE skipped (%s): last kick was %d s ago",reason,now-previous);}
        return;
    }
    lastSaveAt=now;
    const int mode=vkKickMode.load();
    unsigned outer=0;
    __try{outer=*reinterpret_cast<const unsigned*>(session+kOffStage);}__except(EXCEPTION_EXECUTE_HANDLER){outer=0xffffffffu;}
    Log("SAVE kick mode=%d: %s (session=%p outer=%u sub=%u)",mode,reason,reinterpret_cast<void*>(session),outer,SessionState());
    __try{
        switch(mode){
        case 2:*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 3:*reinterpret_cast<unsigned*>(session+kOffStage)=0;*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 4:*reinterpret_cast<unsigned*>(session+kOffStage)=7;*reinterpret_cast<unsigned*>(session+0x100)=0;break;
        case 6:{/* 直接调游戏自己的 StartStage(session, stage, ?, slot) */
            int slot6=0;
            __try{slot6=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}__except(EXCEPTION_EXECUTE_HANDLER){slot6=0;}
            reinterpret_cast<void(__fastcall*)(void*,int,int,int)>(base+0xc44790)(
                reinterpret_cast<void*>(session),kSaveStage,0,slot6);
            break;}
        case 5:{/* 像游戏自己的请求队列那样进入存档阶段：槽位 + 阶段 + 子状态 */
            int slot=0;
            __try{slot=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}__except(EXCEPTION_EXECUTE_HANDLER){slot=0;}
            if(SetSessionStage(session,kSaveStage,slot)){
                saveSeqStage=kSaveStage;                 // 这一段走完再踢阶段 5（SlotData）
                saveStageSeen=0;saveStageSetAt=GetTickCount64();
                Log("SAVE kick: stage %u slot %d (next stage %u)",kSaveStage,slot,kSaveSlotStage);
            }
            break;}
        default:saveFlowOriginal(reinterpret_cast<void*>(session));break;
        }
    }__except(EXCEPTION_EXECUTE_HANDLER){Log("SAVE kick mode=%d faulted",mode);saveStepAbort();return;}
    unsigned outerAfter=0,subAfter=0;
    __try{outerAfter=*reinterpret_cast<const unsigned*>(session+kOffStage);subAfter=*reinterpret_cast<const unsigned*>(session+0x100);}
    __except(EXCEPTION_EXECUTE_HANDLER){outerAfter=subAfter=0xffffffffu;}
    Log("SAVE kick returned: outer=%u sub=%u",outerAfter,subAfter);
    if(outerAfter!=kIdleStage)saveInFlight=1;   // 阶段离开了空闲：我们的存档在跑
    else if(saveSeqStage.load())saveInFlight=1;  // 可能被分发器立刻消费掉，序列状态才准
}/* 会话被拆之前，如果游戏自己的存档状态机还在跑，等它走完（最多 4 秒），避免半截存档。 */
static void WaitForPendingSave(const char* where){
    if(!saveInFlight.load())return;                 // 只等我们自己踢出去的那次存档
    const ULONGLONG now=GetTickCount64();
    if(now-saveWaitDone.load()<500)return;          // 同一次拆除只等一次（会话析构+管理器析构是连环的）
    const ULONGLONG limit=now+2500;
    Log("SAVE in flight at %s; waiting for the stage to finish",where);
    while(saveInFlight.load()&&GetTickCount64()<limit)Sleep(10);
    saveWaitDone=GetTickCount64();
    Log("SAVE wait done at %s: in_flight=%d",where,saveInFlight.load());
}
/* Worker 每轮检查：阶段回到空闲就说明我们踢的存档跑完了。 */
static void NoteSaveProgress(){
    if(!saveInFlight.load())return;
    const uintptr_t session=sessionObject.load();
    const uintptr_t manager=ManagerFromSession(session);
    int slot=0;
    __try{if(manager)slot=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}
    __except(EXCEPTION_EXECUTE_HANDLER){slot=0;}
    const unsigned stage=SessionStage();
    if(stage!=kIdleStage){saveStageSeen=1;return;}          // 阶段在跑，记下"确实起来了"
    const ULONGLONG now=GetTickCount64();
    if(!saveStageSeen.load()){
        /* 写下去之后游戏还没接手：给它 150 ms；仍不动就重写（最多 5 次）。 */
        if(now-saveStageSetAt.load()<150)return;
        static int retries=0;
        const int pending=saveSeqStage.load();
        if(pending&&retries<5){
            ++retries;
            SetSessionStage(session,static_cast<unsigned>(pending),slot);
            saveStageSetAt=now;
            Log("SAVE stage %d retry %d",pending,retries);
            return;
        }
        retries=0;
        Log("SAVE stage %d never started; giving up",pending);
        saveSeqStage=0;saveInFlight=0;
        return;
    }
    /* 阶段跑起来并且已经回到空闲：这一段完成。 */
    static int completions=0;
    const int seq=saveSeqStage.load();
    if(seq==static_cast<int>(kSaveStage)){
        if(SetSessionStage(session,kSaveSlotStage,slot)){
            saveSeqStage=kSaveSlotStage;
            saveStageSeen=0;saveStageSetAt=now;
            Log("SAVE stage %u done; kicking stage %u (SlotData, slot %d)",kSaveStage,kSaveSlotStage,slot);
        }else{
            saveSeqStage=0;saveInFlight=0;saveStageSeen=0;
            Log("SAVE second stage failed to start");
        }
        return;
    }
    if(seq==static_cast<int>(kSaveSlotStage)){
        saveSeqStage=0;saveInFlight=0;saveStageSeen=0;
        Log("SAVE sequence complete (stages %u and %u, run %d)",kSaveStage,kSaveSlotStage,++completions);
    }
}

static void ProbeReport(){
    const uintptr_t m=saveManager.load();
    const uintptr_t session=sessionObject.load();
    uintptr_t vtable=0;bool match=false;
    __try{
        if(m){vtable=*reinterpret_cast<const uintptr_t*>(m);match=vtable==base+kVtableSaveManager;}
    }__except(EXCEPTION_EXECUTE_HANDLER){vtable=0;match=false;}
    if(probeVerbose.load())Log("PROBE instance=%p vtable=%p match=%d source=%d updates=%u",reinterpret_cast<void*>(m),
        reinterpret_cast<void*>(vtable),int(match),saveManagerSource.load(),updates.load());
    unsigned outer=0xffffffffu,sub=0xffffffffu;
    __try{
        if(session){outer=*reinterpret_cast<const unsigned*>(session+kOffStage);sub=*reinterpret_cast<const unsigned*>(session+0x100);}
    }__except(EXCEPTION_EXECUTE_HANDLER){outer=sub=0xffffffffu;}
    if(probeVerbose.load())Log("PROBE session=%p outer=%u sub=%u alive=%d",reinterpret_cast<void*>(session),outer,sub,int(SessionAlive()));
}
/* 玩家 update 停了就说明世界已经不在：用来判断"某次操作后多久世界消失"。 */
static void NoteUpdateGap(){
    static ULONGLONG last=0;
    const ULONGLONG now=GetTickCount64();
    if(last&&now-last>1000)Log("PROBE gameplay update stopped for %llu ms",now-last);
    last=now;
}
/* ---- 会话/管理器析构：只等我们自己踢出去的那次存档落完，避免半截存档 ---- */
using GenericFn=void*(__fastcall*)(void*,void*,void*,void*);
static GenericFn sessionDtorOriginal,sessionDeleterOriginal;
/* 四个 load 请求入口：code 2/3/4/5。它们只在进出关卡时调用，正好用来白拿管理器实例。 */
using LoadRequest=bool(__fastcall*)(void*,void*,void*);
static LoadRequest load2Original,load3Original,load4Original,load5Original;
static void LogTransition(const char* tag,uintptr_t caller){
    const uintptr_t m=saveManager.load();
    uintptr_t vtable=0;bool match=false;
    __try{if(m){vtable=*reinterpret_cast<const uintptr_t*>(m);match=vtable==base+kVtableSaveManager;}}
    __except(EXCEPTION_EXECUTE_HANDLER){vtable=0;match=false;}
    if(probeVerbose.load())Log("PROBE TRANS %s caller=+0x%llx updates=%u manager=%p ok=%d",tag,
        (unsigned long long)caller,updates.load(),reinterpret_cast<void*>(m),int(match));
}
static void CaptureManager(void* manager,const char* tag,int code,uintptr_t caller){
    uintptr_t vtable=0;bool match=false;
    __try{vtable=*reinterpret_cast<const uintptr_t*>(manager);match=vtable==base+kVtableSaveManager;}
    __except(EXCEPTION_EXECUTE_HANDLER){vtable=0;match=false;}
    if(match&&!saveManager.load()){
        saveManager=reinterpret_cast<uintptr_t>(manager);saveManagerSource=3;
        Log("PROBE instance captured from %s: %p",tag,manager);
    }
    if(probeVerbose.load())Log("PROBE REQ %s code=%d caller=+0x%llx manager_ok=%d updates=%u",tag,code,
        (unsigned long long)caller,int(match),updates.load());
}
static void* __fastcall SessionDtorHook(void* a,void* b,void* c,void* d){
    const uintptr_t caller=CallerRva();
    /* 玩家按 F10 后马上退到标题/退出：等那次存档落完再拆会话。 */
    WaitForPendingSave("session dtor");
    void* result=sessionDtorOriginal(a,b,c,d);
    LogTransition("session dtor",caller);
    return result;
}
static void* __fastcall SessionDeleterHook(void* a,void* b,void* c,void* d){
    const uintptr_t caller=CallerRva();
    void* result=sessionDeleterOriginal(a,b,c,d);
    LogTransition("session deleter",caller);
    return result;
}
using SessionUpdate=void(__fastcall*)(void*);
static SessionUpdate sessionUpdateOriginal;
/* session+0xe8 是"管理器 holder"，*holder 才是管理器；用 vtable 做结构校验。 */
static bool ValidSession(uintptr_t session){
    if(!session)return false;
    uintptr_t holder=0,manager=0,vtable=0;
    __try{
        holder=*reinterpret_cast<const uintptr_t*>(session+kOffManagerHolder);
        if(holder)manager=*reinterpret_cast<const uintptr_t*>(holder);
        if(manager)vtable=*reinterpret_cast<const uintptr_t*>(manager);
    }__except(EXCEPTION_EXECUTE_HANDLER){return false;}
    if(vtable!=base+kVtableSaveManager)return false;
    const uintptr_t known=saveManager.load();
    return !known||known==manager;
}
/* 会话分发器每帧都会被调用，入口 rcx 就是会话对象：注入晚于读档也能立刻拿到。 */
/* 会话 +0xe8 是"管理器 holder"，*holder 才是管理器：注入晚于读档时靠它补上实例。 */
static uintptr_t ManagerFromSession(uintptr_t session){
    if(!session)return 0;
    uintptr_t holder=0,manager=0;
    __try{
        holder=*reinterpret_cast<const uintptr_t*>(session+kOffManagerHolder);
        if(holder)manager=*reinterpret_cast<const uintptr_t*>(holder);
    }__except(EXCEPTION_EXECUTE_HANDLER){return 0;}
    return manager;
}
static void* __fastcall SessionUpdateHook(void* session){
    const uintptr_t candidate=reinterpret_cast<uintptr_t>(session);
    if(candidate&&candidate!=sessionObject.load()&&ValidSession(candidate)){
        const uintptr_t previous=sessionObject.exchange(candidate);
        if(probeVerbose.load())Log("PROBE session %s: %p -> %p",previous?"changed":"captured",
            reinterpret_cast<void*>(previous),reinterpret_cast<void*>(candidate));
        const uintptr_t manager=ManagerFromSession(candidate);
        if(manager&&saveManager.load()!=manager){
            saveManager=manager;saveManagerSource=4;
            Log("PROBE instance captured from session chain: %p",reinterpret_cast<void*>(manager));
        }
    }
    /* 阶段迁移打点：存档 3→5→1 已确认。 */
    static unsigned lastStage=0xffffffffu;
    const unsigned stage=SessionStage();
    if(stage!=lastStage&&stage!=0xffffffffu){
        if(probeVerbose.load())Log("PROBE stage %u -> %u",lastStage,stage);
        lastStage=stage;
    }
    sessionUpdateOriginal(session);
    return nullptr;
}
static void* __fastcall SaveFlowHook(void* session){    const uintptr_t caller=CallerRva();
    unsigned flowStateBefore=0xffffffffu;
    __try{flowStateBefore=*reinterpret_cast<unsigned*>(uintptr_t(session)+kOffFlowState);}
    __except(EXCEPTION_EXECUTE_HANDLER){flowStateBefore=0xffffffffu;}
    const bool first=!sessionObject.load()&&session!=nullptr;
    if(first)sessionObject=reinterpret_cast<uintptr_t>(session);
    saveFlowOriginal(session);
    if(first)Log("PROBE session captured from save flow: %p",session);
    else Log("PROBE TRANS save flow caller=+0x%llx upstream_state=%u state_now=%u",(unsigned long long)caller,
        flowStateBefore,SessionState());
    return nullptr;
}
static bool __fastcall Load2Hook(void* manager,void* slot,void* meta){
    const uintptr_t caller=CallerRva();const bool ok=load2Original(manager,slot,meta);
    CaptureManager(manager,"load2",2,caller);return ok;
}
static bool __fastcall Load3Hook(void* manager,void* slot,void* meta){
    const uintptr_t caller=CallerRva();const bool ok=load3Original(manager,slot,meta);
    CaptureManager(manager,"load3",3,caller);return ok;
}
static bool __fastcall Load4Hook(void* manager,void* slot,void* meta){
    const uintptr_t caller=CallerRva();const bool ok=load4Original(manager,slot,meta);
    CaptureManager(manager,"load4",4,caller);return ok;
}
static bool __fastcall Load5Hook(void* manager,void* slot,void* meta){
    const uintptr_t caller=CallerRva();const bool ok=load5Original(manager,slot,meta);
    CaptureManager(manager,"load5",5,caller);return ok;
}
static bool Install(){
    static const unsigned char a[]={0x40,0x55,0x53,0x57,0x41,0x56,0x48,0x8b,0xec,0x48,0x83,0xec,0x78,0x48,0x8b,0xf9};
    static const unsigned char b[]={0x48,0x89,0x5c,0x24,0x10,0x56,0x48,0x83,0xec,0x20,0x8b,0xf2};
    static const unsigned char c[]={0x48,0x89,0x5c,0x24,0x08,0x44,0x89,0x44,0x24,0x18,0x88,0x54,0x24,0x10};
    static const unsigned char d[]={0x40,0x53,0x48,0x83,0xec,0x30,0x48,0x63,0xda,0x48,0x8b,0x11};
    static const unsigned char e[]={0xe8,0x6c,0x6d,0x6b,0x00}; // 60890f -> cbf680
    static const unsigned char f[]={0xe8,0x52,0x71,0x6b,0x00}; // 608929 -> cbfa80
    if(!Match(0x608730,a,sizeof a)||!Match(0xcbf680,b,sizeof b)||!Match(0xcbfa80,c,sizeof c)||!Match(0xcc04a0,d,sizeof d)||!Match(0x60890f,e,sizeof e)||!Match(0x608929,f,sizeof f))return false;
    auto s=MH_Initialize();
    if(s!=MH_OK){Log("MH_Initialize: %s",MH_StatusToString(s));return false;}
    struct Hook{uintptr_t rva;void* fn;void** original;bool required;};
    Hook hooks[]={
        {0x608730,reinterpret_cast<void*>(&UpdateHook),reinterpret_cast<void**>(&updateOriginal),true},
        {0xcbf680,reinterpret_cast<void*>(&SelectHook),reinterpret_cast<void**>(&selectOriginal),true},
        {0xcbfa80,reinterpret_cast<void*>(&ResolveHook),reinterpret_cast<void**>(&resolveOriginal),true}};
    for(const auto& h:hooks){
        s=MH_CreateHook(reinterpret_cast<void*>(base+h.rva),h.fn,h.original);
        if(s!=MH_OK){
            Log("MH_CreateHook %llx: %s",(unsigned long long)h.rva,MH_StatusToString(s));
            if(h.required){MH_Uninitialize();return false;}
            continue;
        }
        MH_QueueEnableHook(reinterpret_cast<void*>(base+h.rva));
    }
    s=MH_ApplyQueued();
    if(s!=MH_OK){Log("MH_ApplyQueued: %s",MH_StatusToString(s));MH_Uninitialize();return false;}
    /* 存档探针 hook：任何一条不匹配或装不上都只跳过它自己，绝不影响武器功能。 */
    static const unsigned char p7[]={0x40,0x53,0x48,0x83,0xec,0x60,0x48,0x8b,0xd9,0x48,0x81,0xc1,0x80,0x05};
    static const unsigned char p8[]={0x89,0x54,0x24,0x10,0x4c,0x8b,0xdc,0x53,0x48,0x81,0xec,0x80,0x00,0x00};
    static const unsigned char p6[]={0x40,0x53,0x48,0x83,0xec,0x60,0x48,0x8b,0xd9,0x48,0x81,0xc1,0x80,0x05};
    static const unsigned char pc[]={0x48,0x89,0x5c,0x24,0x10,0x57,0x48,0x81,0xec,0xb0,0x00,0x00,0x00};
    static const unsigned char pd[]={0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x6c,0x24,0x10,0x48,0x89,0x74,0x24,0x18,0x57,0x48,0x83,0xec,0x20};
    struct ProbeHook{const char* name;uintptr_t rva;const unsigned char* bytes;size_t size;void* fn;void** original;};
    const ProbeHook probe[]={
        {"save GameData",0x102e3d0,p7,sizeof p7,reinterpret_cast<void*>(&Request7Hook),reinterpret_cast<void**>(&request7Original)},
        {"save SlotData",0x102e430,p8,sizeof p8,reinterpret_cast<void*>(&Request8Hook),reinterpret_cast<void**>(&request8Original)},
        {"save SystemData",0x102e510,p6,sizeof p6,reinterpret_cast<void*>(&Request6Hook),reinterpret_cast<void**>(&request6Original)},
        {"manager ctor",0x102c9b0,pc,sizeof pc,reinterpret_cast<void*>(&ManagerCtorHook),reinterpret_cast<void**>(&ctorOriginal)},
        {"manager dtor",0x102cc10,pd,sizeof pd,reinterpret_cast<void*>(&ManagerDtorHook),reinterpret_cast<void**>(&dtorOriginal)},
    };
    for(const auto& h:probe){
        if(memcmp(reinterpret_cast<void*>(base+h.rva),h.bytes,h.size)!=0){
            Log("PROBE skip %s: bytes at RVA %llx do not match",h.name,(unsigned long long)h.rva);
            continue;
        }
        s=MH_CreateHook(reinterpret_cast<void*>(base+h.rva),h.fn,h.original);
        if(s!=MH_OK){Log("PROBE skip %s: MH_CreateHook %s",h.name,MH_StatusToString(s));continue;}
        MH_QueueEnableHook(reinterpret_cast<void*>(base+h.rva));
    }
    /* 离开游戏路径 + load 请求入口的候选 hook（同样逐条独立、失败只跳过）。 */
    static const unsigned char q2[]={0x48,0x83,0xec,0x68,0x48,0xc7,0x44,0x24,0x58,0x00,0x00,0x00,0x00,0x80,0xb9};
    static const unsigned char q5[]={0x89,0x54,0x24,0x10,0x4c,0x8b,0xdc,0x53,0x48,0x81,0xec,0x80,0x00,0x00};
    static const unsigned char qs[]={0x48,0x89,0x5c,0x24,0x08,0x57,0x48,0x83,0xec,0x20,0x48,0x8b,0xd9,0x48,0x8b,0x89};
    static const unsigned char qd[]={0x40,0x53,0x48,0x83,0xec,0x20,0x48,0x8b,0x59,0x08,0x48,0x85,0xdb,0x74,0x20,0x48};
    static const unsigned char qf[]={0x4c,0x8b,0xdc,0x49,0x89,0x7b,0x20,0x55,0x49,0x8d,0xab,0xa8,0xfb,0xff,0xff,0x48};
    static const unsigned char qs2[]={0x48,0x89,0x5c,0x24,0x10,0x48,0x89,0x74,0x24,0x18,0x48,0x89,0x7c,0x24,0x20,0x55};
    const ProbeHook probe2[]={
        {"session update",0xc44980,qs2,sizeof qs2,reinterpret_cast<void*>(&SessionUpdateHook),reinterpret_cast<void**>(&sessionUpdateOriginal)},
        {"save flow",0xc460b0,qf,sizeof qf,reinterpret_cast<void*>(&SaveFlowHook),reinterpret_cast<void**>(&saveFlowOriginal)},
        {"load2",0x102de10,q2,sizeof q2,reinterpret_cast<void*>(&Load2Hook),reinterpret_cast<void**>(&load2Original)},
        {"load3",0x102dfe0,q2,sizeof q2,reinterpret_cast<void*>(&Load3Hook),reinterpret_cast<void**>(&load3Original)},
        {"load4",0x102dcd0,q2,sizeof q2,reinterpret_cast<void*>(&Load4Hook),reinterpret_cast<void**>(&load4Original)},
        {"load5",0x102dd20,q5,sizeof q5,reinterpret_cast<void*>(&Load5Hook),reinterpret_cast<void**>(&load5Original)},
        {"session dtor",0xc420e0,qs,sizeof qs,reinterpret_cast<void*>(&SessionDtorHook),reinterpret_cast<void**>(&sessionDtorOriginal)},
        {"session deleter",0x965fb0,qd,sizeof qd,reinterpret_cast<void*>(&SessionDeleterHook),reinterpret_cast<void**>(&sessionDeleterOriginal)},
    };
    for(const auto& h:probe2){
        if(memcmp(reinterpret_cast<void*>(base+h.rva),h.bytes,h.size)!=0){
            Log("PROBE skip %s: bytes at RVA %llx do not match",h.name,(unsigned long long)h.rva);
            continue;
        }
        s=MH_CreateHook(reinterpret_cast<void*>(base+h.rva),h.fn,h.original);
        if(s!=MH_OK){Log("PROBE skip %s: MH_CreateHook %s",h.name,MH_StatusToString(s));continue;}
        MH_QueueEnableHook(reinterpret_cast<void*>(base+h.rva));
    }
    s=MH_ApplyQueued();
    if(s!=MH_OK)Log("PROBE MH_ApplyQueued: %s",MH_StatusToString(s));
    Log("READY v0.2+probe: hooks installed; weapon keys come from [Keys], the manual save key from [Save] TestKey");
    return true;
}
static DWORD WINAPI Worker(void*){
    GetModuleFileNameW(self,configPath,MAX_PATH);
    auto slash=wcsrchr(configPath,L'\\');if(!slash)return 0;
    slash[1]=0;wcscpy_s(logPath,configPath);
    wcscat_s(configPath,L"SixSlot.ini");wcscat_s(logPath,L"SixSlot.log");
    base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    Log("Loading NG4 extra weapon keys, PID %lu, module %p",GetCurrentProcessId(),reinterpret_cast<void*>(base));
    LoadConfig();if(!Install())return 0;
    /* 不再扫内存（实测 184 秒且把工作集顶上 5 GB）：实例改由 load/save 请求 hook 与构造 hook 提供。 */
    Log("PROBE watching save directory under %%LOCALAPPDATA%%\\NINJAGAIDEN4");
    wchar_t stopName[96],startName[96],stateName[96];
    swprintf_s(stopName,L"Local\\NG4SixSlot_Stop_%lu",GetCurrentProcessId());
    swprintf_s(startName,L"Local\\NG4SixSlot_Start_%lu",GetCurrentProcessId());
    swprintf_s(stateName,L"Local\\NG4SixSlot_Enabled_%lu",GetCurrentProcessId());
    HANDLE stop=CreateEventW(nullptr,FALSE,FALSE,stopName);
    HANDLE start=CreateEventW(nullptr,FALSE,FALSE,startName);
    HANDLE state=CreateEventW(nullptr,TRUE,TRUE,stateName);
    bool last5=true,last6=true,lastTest=false;
    FILETIME lastWrite{};
    ULONGLONG lastCheck=0,lastReport=0,lastProbe=0;
    while(true){
        if(stop && WaitForSingleObject(stop,0)==WAIT_OBJECT_0){enabled=false;if(state)ResetEvent(state);request=0;Log("DISABLED by launcher; native input only");}
        if(start && WaitForSingleObject(start,0)==WAIT_OBJECT_0){enabled=true;if(state)SetEvent(state);request=0;Log("ENABLED by launcher");}
        const auto now=GetTickCount64();
        /* 每秒热重载配置（面板改开关不用重启游戏）+ 盯一眼存档文件的写入时间（验证 F10 真的落盘）。 */
        if(now-lastCheck>1000){
            lastCheck=now;WIN32_FILE_ATTRIBUTE_DATA attr{};
            if(GetFileAttributesExW(configPath,GetFileExInfoStandard,&attr) && CompareFileTime(&lastWrite,&attr.ftLastWriteTime)!=0){lastWrite=attr.ftLastWriteTime;LoadConfig();}
            WatchSaveFiles();
        }
        /* F10 兜底：人在菜单里时玩家 update 停了，游戏线程不会来消费踢存档请求，这里补踢一次。
           只在会话空闲时踢，KickGameSave 自带 2 秒去重，不会重复写盘。 */
        const ULONGLONG pendingKick=kickRequest.load();
        if(pendingKick&&now-pendingKick>400){
            ULONGLONG expected=pendingKick;
            if(kickRequest.compare_exchange_strong(expected,0))KickGameSave("manual save key (worker)");
        }
        NoteSaveProgress();
        if(probeVerbose.load()&&now-lastProbe>2000){lastProbe=now;ProbeReport();}
        DWORD foreground=0;GetWindowThreadProcessId(GetForegroundWindow(),&foreground);
        const int key5Vk=vk5.load(),key6Vk=vk6.load();
        bool k5=key5Vk!=0 && (GetAsyncKeyState(key5Vk)&0x8000)!=0;
        bool k6=key6Vk!=0 && (GetAsyncKeyState(key6Vk)&0x8000)!=0;
        const int testVk=vkSaveTest.load();
        const bool testKeyDown=testVk!=0 && (GetAsyncKeyState(testVk)&0x8000)!=0;
        const bool modifiers=(GetAsyncKeyState(VK_CONTROL)&0x8000)||(GetAsyncKeyState(VK_MENU)&0x8000)||(GetAsyncKeyState(VK_SHIFT)&0x8000);
        if(foreground==GetCurrentProcessId() && !modifiers){
            if(enabled){
                if(k5&&!last5)request=(now<<8)|5;
                else if(k6&&!last6)request=(now<<8)|6;
            }else request=0;
            /* 主动存档只受 [Save] TestKey 控制：六槽武器开关关掉也照样能按 F10 存档。 */
            if(testKeyDown&&!lastTest)kickRequest=now;
        }else request=0;
        last5=k5;last6=k6;lastTest=testKeyDown;
        if(now-lastReport>10000){
            lastReport=now;
            Log("STATUS enabled=%d updates=%u player=%p weapon=%d keys=0x%02x/0x%02x",int(enabled.load()),updates.load(),reinterpret_cast<void*>(lastPlayer.load()),currentWeapon.load(),vk5.load(),vk6.load());
        }
        Sleep(4);
    }
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){
    if(reason==DLL_PROCESS_ATTACH){self=module;DisableThreadLibraryCalls(module);HANDLE t=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);if(t)CloseHandle(t);}
    return TRUE;
}
