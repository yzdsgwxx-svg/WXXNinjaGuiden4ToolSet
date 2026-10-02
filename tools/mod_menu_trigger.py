"""改触发时机：菜单打开时就存档。

实测两个"离开"动作（返回标题栏界面 / 退出游戏）都是**先拆会话**——等会话析构通知到手，
游戏已经不再跑阶段分发器，踢了也没人执行（日志：kick 后 stage 一直没动、白等 8 秒）。
而 SE_Sys_BackToTitle 那个挂点属于"死亡后回标题"，不是暂停菜单那条路。

所以改成：**玩家 update 停了 + 会话仍在空闲阶段 = 人在菜单里** → 立刻存一次。
覆盖返回标题 / 退出游戏 / 返回记录点所有离开路径。
同时：会话析构只做一次有界等待（不再 4+4 秒连环等），且不再在析构时踢（来不及）。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 开关 + 玩家 update 时间戳
old = 'static std::atomic<int> probeVerbose{1};  // [Save] Probe：1=诊断日志全开'
assert old in s, 'verbose'
s = s.replace(old, old + '''
static std::atomic<int> saveOnPause{1};      // [Save] SaveOnPause：菜单打开就存档
static std::atomic<ULONGLONG> lastPlayerTick{0};  // 玩家 update 的最后时刻（判断是否进了菜单）
static std::atomic<ULONGLONG> saveWaitDone{0};    // 上一次等存档结束的时刻（避免连环等）''', 1)

# 2) LoadConfig 读取
old = '    probeVerbose=GetPrivateProfileIntW(L"Save",L"Probe",1,configPath)?1:0;'
assert old in s, 'verbose read'
s = s.replace(old, old + '\n    saveOnPause=GetPrivateProfileIntW(L"Save",L"SaveOnPause",1,configPath)?1:0;', 1)
old = '    Log("Diagnostics: probe=%s kick mode=%d",probeVerbose.load()?"on":"off",kickMode);'
assert old in s, 'diag log'
s = s.replace(old, old + '\n    Log("Save on pause menu: %s",saveOnPause.load()?"on":"off");', 1)

# 3) UpdateHook 记时间戳
old = '''static void __fastcall UpdateHook(void* player){
    ++updates;
    NoteUpdateGap();'''
assert old in s, 'update hook'
s = s.replace(old, '''static void __fastcall UpdateHook(void* player){
    ++updates;
    lastPlayerTick=GetTickCount64();
    NoteUpdateGap();''', 1)

# 4) 会话析构：不再踢（来不及），只做一次有界等待
old = '''    /* 会话被拆之前把存档补上，并等写盘落完，避免半截存档。 */
    if(autoSaveOn.load()){
        const int now=int(GetTickCount64()/1000);
        if(now-lastSaveAt.load()>3)KickGameSave("session teardown");
    }
    WaitForPendingSave("session dtor");'''
assert old in s, 'dtor kick'
s = s.replace(old, '''    /* 这里不再踢存档：实测确认时刻会话已经在拆、游戏不再跑阶段分发器，踢了也不会执行。
       只等"之前踢出去的那次"落完，避免半截存档。 */
    WaitForPendingSave("session dtor");''', 1)

# 5) 有界等待：总时长 2.5 秒、且两次析构（会话/管理器）不重复等
old = '''static void WaitForPendingSave(const char* where){
    if(!saveInFlight.load())return;                 // 只等我们自己踢出去的那次存档
    const ULONGLONG limit=GetTickCount64()+4000;'''
assert old in s, 'wait head'
s = s.replace(old, '''static void WaitForPendingSave(const char* where){
    if(!saveInFlight.load())return;                 // 只等我们自己踢出去的那次存档
    const ULONGLONG now=GetTickCount64();
    if(now-saveWaitDone.load()<500)return;          // 同一次拆除只等一次（会话析构+管理器析构是连环的）
    const ULONGLONG limit=now+2500;''', 1)
old = '    Log("SAVE wait done at %s: in_flight=%d",where,saveInFlight.load());'
assert old in s, 'wait tail'
s = s.replace(old, '    saveWaitDone=GetTickCount64();\n' + old, 1)

# 6) 菜单检测：会话 update 里做（游戏线程、每帧）
old = '''    /* 阶段迁移打点：存档 3→5→1 已确认，退出/回标题走哪一步还没测过。 */'''
assert old in s, 'stage log anchor'
s = s.replace(old, '''    /* 菜单检测：玩家 update 停了、会话仍是空闲阶段 → 人在菜单里（读档时阶段非空闲，天然排除）。
       两个"离开"动作都先拆会话，等到那一刻再存已经来不及，所以在这里先存一次。 */
    if(autoSaveOn.load()&&saveOnPause.load()&&SessionStage()==kIdleStage&&lastPlayerTick.load()){
        const ULONGLONG now=GetTickCount64();
        if(now-lastPlayerTick.load()>1500)KickGameSave("menu opened");
    }
    /* 阶段迁移打点：存档 3→5→1 已确认。 */''', 1)

# 7) KickGameSave 的 8 秒去重放宽到 20 秒（菜单里可能反复进出）
old = '    if(previous&&now-previous<8){Log("SAVE skipped (%s): last kick was %d s ago",reason,now-previous);return;}'
assert old in s, 'dedupe'
s = s.replace(old, '    if(previous&&now-previous<20){Log("SAVE skipped (%s): last kick was %d s ago",reason,now-previous);return;}', 1)

p.write_text(s, encoding='utf-8')
print('trigger moved to menu-open; waits bounded')
