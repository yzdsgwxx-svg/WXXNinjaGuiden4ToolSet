"""存档两段化（修正版，匹配当前源码文本）。

阶段 3 = GameData.dat + SystemData.vdf；阶段 5 = SlotData_{n}.dat + GameData.dat。
踢一次完整存档 = 踢阶段 3 → 等它回空闲 → 再踢阶段 5（带重试，防止写入被分发器盖掉）。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 状态
old = 'static std::atomic<int> saveInFlight{0};   // 1 = 我们踢出去的存档阶段还没走完'
assert old in s, 'atomics'
s = s.replace(old, old + '''
static std::atomic<int> saveSeqStage{0};    // 0=空闲；3=阶段3 已踢；5=阶段5 已踢
static std::atomic<ULONGLONG> saveStageRetry{0};''', 1)

# 2) 阶段 5 常量
old = 'static constexpr unsigned kIdleStage=1;               // 阶段 1 = 空闲（请求队列处理完就回这里）'
assert old in s, 'idle const'
s = s.replace(old, old + '\nstatic constexpr unsigned kSaveSlotStage=5;           // 阶段 5 = SlotData_{n}.dat + GameData.dat', 1)

# 3) 抽出 SetSessionStage
old = 'static void KickGameSave(const char* reason){'
assert old in s, 'kick head'
s = s.replace(old, '''/* 写"进入某阶段"的三个字段——游戏自己的 StartStage(0xc44790) 就是这么做的。 */
static bool SetSessionStage(uintptr_t session,unsigned stage,int slot){
    if(!session)return false;
    __try{
        *reinterpret_cast<unsigned*>(session+kOffStageSlot)=static_cast<unsigned>(slot);
        *reinterpret_cast<unsigned*>(session+kOffStage)=stage;
        *reinterpret_cast<unsigned*>(session+kOffFlowState)=0;
        return true;
    }__except(EXCEPTION_EXECUTE_HANDLER){Log("SAVE stage %u write faulted",stage);return false;}
}
''' + old, 1)

# 4) case 5 用实际文本
old = '''        case 5:{/* 像游戏自己的请求队列那样进入存档阶段：槽位 + 阶段 + 子状态 */
            int slot=0;
            __try{slot=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}__except(EXCEPTION_EXECUTE_HANDLER){slot=0;}
            *reinterpret_cast<unsigned*>(session+0xf4)=static_cast<unsigned>(slot);
            *reinterpret_cast<unsigned*>(session+kOffStage)=kSaveStage;
            *reinterpret_cast<unsigned*>(session+0x100)=0;
            Log("SAVE kick: stage %u slot %d",kSaveStage,slot);
            break;}'''
assert old in s, 'case5'
new = '''        case 5:{/* 像游戏自己的请求队列那样进入存档阶段：槽位 + 阶段 + 子状态 */
            int slot=0;
            __try{slot=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}__except(EXCEPTION_EXECUTE_HANDLER){slot=0;}
            if(SetSessionStage(session,kSaveStage,slot)){
                saveSeqStage=kSaveStage;                 // 这一段走完再踢阶段 5（SlotData）
                Log("SAVE kick: stage %u slot %d (next stage %u)",kSaveStage,slot,kSaveSlotStage);
            }
            break;}'''
s = s.replace(old, new, 1)

# 5) NoteSaveProgress 两段推进
old = '''static void NoteSaveProgress(){
    if(saveInFlight.load()&&SessionStage()==kIdleStage){
        saveInFlight=0;
        Log("SAVE stage finished (back to idle)");
    }
}'''
assert old in s, 'note progress'
new = '''static void NoteSaveProgress(){
    if(!saveInFlight.load()||SessionStage()!=kIdleStage)return;
    const uintptr_t session=sessionObject.load();
    const uintptr_t manager=ManagerFromSession(session);
    int slot=0;
    __try{if(manager)slot=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}
    __except(EXCEPTION_EXECUTE_HANDLER){slot=0;}
    if(saveSeqStage.load()==static_cast<int>(kSaveStage)){
        /* 第一段（GameData+SystemData）走完 → 踢第二段 SlotData+GameData。 */
        if(SetSessionStage(session,kSaveSlotStage,slot)){
            saveSeqStage=kSaveSlotStage;
            saveStageRetry=GetTickCount64()+50;
            Log("SAVE stage %u done; kicking stage %u (SlotData, slot %d)",kSaveStage,kSaveSlotStage,slot);
        }else{
            saveSeqStage=0;saveInFlight=0;Log("SAVE second stage failed to start");
        }
        return;
    }
    if(saveSeqStage.load()==static_cast<int>(kSaveSlotStage)){
        /* 第二段已踢：给它 50 ms 落地；若阶段仍空闲说明被分发器盖掉，重写（最多 5 次）。 */
        if(GetTickCount64()<saveStageRetry.load())return;
        static int retries=0;
        if(retries<5){
            ++retries;
            SetSessionStage(session,kSaveSlotStage,slot);
            saveStageRetry=GetTickCount64()+50;
            Log("SAVE stage %u retry %d",kSaveSlotStage,retries);
            return;
        }
        retries=0;
        saveSeqStage=0;saveInFlight=0;
        Log("SAVE sequence complete (stages %u and %u)",kSaveStage,kSaveSlotStage);
    }
}'''
s = s.replace(old, new, 1)

# 6) 序列状态也算 in-flight
old = '    if(outerAfter!=kIdleStage)saveInFlight=1;   // 阶段离开了空闲：我们的存档在跑'
assert old in s, 'inflight tail'
s = s.replace(old, old + '\n    else if(saveSeqStage.load())saveInFlight=1;  // 可能被分发器立刻消费掉，序列状态才准', 1)

p.write_text(s, encoding='utf-8')
print('two-stage save sequence wired (fixed patch)')
