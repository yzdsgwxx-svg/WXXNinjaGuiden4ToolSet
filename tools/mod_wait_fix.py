"""修 WaitForPendingSave 误判：只有"我们自己踢的存档阶段还在跑"才等，别把残留的
子状态当成存档在飞（实测在会话析构时白等 4 秒、拖慢回标题）。"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 新增 in-flight 标志
old = 'static std::atomic<int> vkKickMode{5};'
assert old in s
s = s.replace(old, old + '\nstatic std::atomic<int> saveInFlight{0};   // 1 = 我们踢出去的存档阶段还没走完', 1)

# 踢成功就置位（mode 5/6 与直接调状态机都算）
old = '    Log("SAVE kick returned: outer=%u sub=%u",outerAfter,subAfter);'
assert old in s
s = s.replace(old, old + '\n    if(outerAfter!=kIdleStage)saveInFlight=1;   // 阶段离开了空闲：我们的存档在跑', 1)

# 空闲阶段常量
old = 'static constexpr unsigned kSaveStage=3;               // 阶段 3 = GameData+SystemData，之后自动串到 5（SlotData）'
assert old in s
s = s.replace(old, old + '\nstatic constexpr unsigned kIdleStage=1;               // 阶段 1 = 空闲（请求队列处理完就回这里）', 1)

# 等待逻辑改成看 in-flight 标志
old = '''static void WaitForPendingSave(const char* where){
    if(!sessionObject.load())return;
    const unsigned state=SessionState();
    if(state==0||state==0xffffffffu)return;
    const ULONGLONG limit=GetTickCount64()+4000;
    Log("SAVE flow still running at %s (state %u); waiting",where,state);
    while(SessionState()!=0&&GetTickCount64()<limit)Sleep(10);
    Log("SAVE wait done at %s: state=%u",where,SessionState());
}'''
assert old in s
new = '''static void WaitForPendingSave(const char* where){
    if(!saveInFlight.load())return;                 // 只等我们自己踢出去的那次存档
    const ULONGLONG limit=GetTickCount64()+4000;
    Log("SAVE in flight at %s; waiting for the stage to finish",where);
    while(saveInFlight.load()&&GetTickCount64()<limit)Sleep(10);
    Log("SAVE wait done at %s: in_flight=%d",where,saveInFlight.load());
}
/* Worker 每轮检查：阶段回到空闲就说明我们踢的存档跑完了。 */
static void NoteSaveProgress(){
    if(saveInFlight.load()&&SessionStage()==kIdleStage){
        saveInFlight=0;
        Log("SAVE stage finished (back to idle)");
    }
}'''
s = s.replace(old, new, 1)

# 需要一个读外层阶段的小函数 + Worker 调用 NoteSaveProgress
old = 'static unsigned SessionState(){'
assert old in s
s = s.replace(old, '''static unsigned SessionStage(){
    const uintptr_t s=sessionObject.load();
    if(!s)return 0xffffffffu;
    unsigned stage=0xffffffffu;
    __try{stage=*reinterpret_cast<const unsigned*>(s+kOffStage);}
    __except(EXCEPTION_EXECUTE_HANDLER){stage=0xffffffffu;}
    return stage;
}
static unsigned SessionState(){''', 1)

old = '        if(now-lastProbe>2000){lastProbe=now;ProbeReport();}'
assert old in s
s = s.replace(old, '        NoteSaveProgress();\n' + old, 1)

p.write_text(s, encoding='utf-8')
print('wait-for-save fixed')
