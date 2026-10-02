"""[Save] KickMode：可通过 ini 切换"怎么踢存档"，配合 [0xf0]/[0x100] 的实时日志定位正确入口。

模式：
  1 = 直接调存档状态机 0xc460b0（当前实现）
  2 = [session+0x100] = 1（进入外层阶段 0 的存档子状态）
  3 = [session+0xf0] = 0 且 [session+0x100] = 1
  4 = [session+0xf0] = 7（分发器下一个阶段就会调 0xc460b0）
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 全局 + 前向声明
old = 'static std::atomic<int> autoSaveOn{1},lastSaveAt{0},vkSaveTest{0};'
assert old in s
s = s.replace(old, old + '\nstatic std::atomic<int> vkKickMode{1};', 1)

# 2) LoadConfig 读取
old = '''    autoSaveOn=exitSave?1:0;vkSaveTest=testKey;'''
assert old in s
s = s.replace(old, old + '''
    int kickMode=GetPrivateProfileIntW(L"Save",L"KickMode",1,configPath);
    if(kickMode<1||kickMode>4)kickMode=1;
    vkKickMode=kickMode;''', 1)

# 3) KickGameSave 按模式执行
old = '''    Log("SAVE kick: %s (session=%p state=%u)",reason,reinterpret_cast<void*>(session),state);
    saveFlowOriginal(reinterpret_cast<void*>(session));
    Log("SAVE kick returned, state now %u",SessionState());'''
assert old in s
new = '''    const int mode=vkKickMode.load();
    unsigned outer=0;
    __try{outer=*reinterpret_cast<const unsigned*>(session+0xf0);}__except(EXCEPTION_EXECUTE_HANDLER){outer=0xffffffffu;}
    Log("SAVE kick mode=%d: %s (session=%p outer=%u sub=%u)",mode,reason,reinterpret_cast<void*>(session),outer,state);
    __try{
        switch(mode){
        case 2:*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 3:*reinterpret_cast<unsigned*>(session+0xf0)=0;*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 4:*reinterpret_cast<unsigned*>(session+0xf0)=7;*reinterpret_cast<unsigned*>(session+0x100)=0;break;
        default:saveFlowOriginal(reinterpret_cast<void*>(session));break;
        }
    }__except(EXCEPTION_EXECUTE_HANDLER){Log("SAVE kick mode=%d faulted",mode);saveStepAbort();return;}
    unsigned outerAfter=0,subAfter=0;
    __try{outerAfter=*reinterpret_cast<const unsigned*>(session+0xf0);subAfter=*reinterpret_cast<const unsigned*>(session+0x100);}
    __except(EXCEPTION_EXECUTE_HANDLER){outerAfter=subAfter=0xffffffffu;}
    Log("SAVE kick returned: outer=%u sub=%u",outerAfter,subAfter);'''
s = s.replace(old, new, 1)

# saveStepAbort 只是把 lastSaveAt 清掉，避免失败后被 8 秒去重挡住
old = 'static void KickGameSave(const char* reason){'
assert old in s
s = s.replace(old, 'static void saveStepAbort(){lastSaveAt=0;}\n' + old, 1)

# 4) 周期报告带上外层/子状态
old = '''    Log("PROBE session=%p flow_state=%u alive=%d",reinterpret_cast<void*>(session),flowState,int(SessionAlive()));'''
assert old in s
s = s.replace(old, '''    unsigned outer=0xffffffffu,sub=0xffffffffu;
    __try{
        if(session){outer=*reinterpret_cast<const unsigned*>(session+0xf0);sub=*reinterpret_cast<const unsigned*>(session+0x100);}
    }__except(EXCEPTION_EXECUTE_HANDLER){outer=sub=0xffffffffu;}
    Log("PROBE session=%p outer=%u sub=%u alive=%d",reinterpret_cast<void*>(session),outer,sub,int(SessionAlive()));''', 1)

p.write_text(s, encoding='utf-8')
print('kick modes wired')
