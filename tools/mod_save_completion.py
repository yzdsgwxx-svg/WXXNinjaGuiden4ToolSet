"""修 NoteSaveProgress 的完成判定：
只按"回空闲"判断，分不清"阶段跑完了"与"根本没启动"——成功后会白重试 5 次。
改成先看阶段是否真的跑起来过（saveStageSeen），跑过了回空闲就算这一段完成。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 新增 seen / setAt
old = 'static std::atomic<ULONGLONG> saveStageRetry{0};'
assert old in s, 'retry atomic'
s = s.replace(old, '''static std::atomic<ULONGLONG> saveStageRetry{0};
static std::atomic<int> saveStageSeen{0};        // 1 = 本次阶段真的跑起来过（非空闲）
static std::atomic<ULONGLONG> saveStageSetAt{0}; // 我们写下这个阶段的时刻''', 1)

# 2) KickGameSave（mode 5）初始化 seen/setAt
old = '''            if(SetSessionStage(session,kSaveStage,slot)){
                saveSeqStage=kSaveStage;                 // 这一段走完再踢阶段 5（SlotData）
                Log("SAVE kick: stage %u slot %d (next stage %u)",kSaveStage,slot,kSaveSlotStage);
            }'''
assert old in s, 'mode5 body'
s = s.replace(old, '''            if(SetSessionStage(session,kSaveStage,slot)){
                saveSeqStage=kSaveStage;                 // 这一段走完再踢阶段 5（SlotData）
                saveStageSeen=0;saveStageSetAt=GetTickCount64();
                Log("SAVE kick: stage %u slot %d (next stage %u)",kSaveStage,slot,kSaveSlotStage);
            }''', 1)

# 3) 重写 NoteSaveProgress
start = s.index('static void NoteSaveProgress(){')
end = s.index('\n}\n', s.index('SAVE sequence complete', start)) + 3
old_block = s[start:end]
assert 'SAVE sequence complete' in old_block and 'kSaveSlotStage' in old_block, 'old block malformed'
new_block = '''static void NoteSaveProgress(){
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
'''
s = s[:start] + new_block + s[end:]

p.write_text(s, encoding='utf-8')
print('completion detection fixed')
