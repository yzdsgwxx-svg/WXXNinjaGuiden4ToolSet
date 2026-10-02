"""正确触发方式：像游戏自己的请求队列那样进入"存档阶段"。

游戏机制（0xc44790 = StartStage）：
    session->[0xf4] = slot; session->[0xf0] = stage; session->[0x100] = 0;
空闲阶段是 1；存档阶段是 3（0xc464d0 做 GameData+SystemData，之后自动串到阶段 5
0xc468d0 做 SlotData+GameData）。槽位取 manager+0x568（路径拼接用的同一个字段）。
新增 KickMode=5（默认）/ 6（直接调 StartStage API）。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

old = '''        case 2:*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 3:*reinterpret_cast<unsigned*>(session+0xf0)=0;*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 4:*reinterpret_cast<unsigned*>(session+0xf0)=7;*reinterpret_cast<unsigned*>(session+0x100)=0;break;
        default:saveFlowOriginal(reinterpret_cast<void*>(session));break;'''
assert old in s
new = '''        case 2:*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 3:*reinterpret_cast<unsigned*>(session+0xf0)=0;*reinterpret_cast<unsigned*>(session+0x100)=1;break;
        case 4:*reinterpret_cast<unsigned*>(session+0xf0)=7;*reinterpret_cast<unsigned*>(session+0x100)=0;break;
        case 6:{/* 直接调游戏自己的 StartStage(session, stage, ?, slot) */
            int slot6=0;
            __try{slot6=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}__except(EXCEPTION_EXECUTE_HANDLER){slot6=0;}
            reinterpret_cast<void(__fastcall*)(void*,int,int,int)>(base+0xc44790)(
                reinterpret_cast<void*>(session),kSaveStage,0,slot6);
            break;}
        case 5:{/* 像游戏自己的请求队列那样进入存档阶段：槽位 + 阶段 + 子状态 */
            int slot=0;
            __try{slot=*reinterpret_cast<const int*>(manager+kOffSaveSlotIndex);}__except(EXCEPTION_EXECUTE_HANDLER){slot=0;}
            *reinterpret_cast<unsigned*>(session+0xf4)=static_cast<unsigned>(slot);
            *reinterpret_cast<unsigned*>(session+0xf0)=kSaveStage;
            *reinterpret_cast<unsigned*>(session+0x100)=0;
            Log("SAVE kick: stage %u slot %d",kSaveStage,slot);
            break;}
        default:saveFlowOriginal(reinterpret_cast<void*>(session));break;'''
s = s.replace(old, new, 1)

# 阶段常量 + 槽位偏移（0x568 是路径拼接用的槽号字段）
old = 'static constexpr uintptr_t kOffManagerHolder=0xe8,kOffFlowState=0x100;'
assert old in s
s = s.replace(old, 'static constexpr uintptr_t kOffManagerHolder=0xe8,kOffFlowState=0x100;\n'
                   'static constexpr uintptr_t kOffSaveSlotIndex=0x568;   // manager+0x568 = 当前槽号\n'
                   'static constexpr uintptr_t kOffStageSlot=0xf4;        // session+0xf4 = 阶段参数（槽位）\n'
                   'static constexpr uintptr_t kOffStage=kOffSessionStage; // session+0xf0 = 外层阶段\n'
                   'static constexpr unsigned kSaveStage=3;               // 阶段 3 = GameData+SystemData，之后自动串到 5（SlotData）', 1)

# 用 kOffStage/kOffStageSlot 取代散落的魔法数字
s = s.replace('*reinterpret_cast<unsigned*>(session+0xf0)', '*reinterpret_cast<unsigned*>(session+kOffStage)')
s = s.replace('*reinterpret_cast<const unsigned*>(session+0xf0)', '*reinterpret_cast<const unsigned*>(session+kOffStage)')
s = s.replace('outer=*reinterpret_cast<const unsigned*>(session+0xf0)', 'outer=*reinterpret_cast<const unsigned*>(session+kOffStage)')

# 默认模式改成 5
s = s.replace('int kickMode=GetPrivateProfileIntW(L"Save",L"KickMode",1,configPath);',
              'int kickMode=GetPrivateProfileIntW(L"Save",L"KickMode",5,configPath);', 1)
s = s.replace('if(kickMode<1||kickMode>4)kickMode=1;', 'if(kickMode<1||kickMode>6)kickMode=5;', 1)
s = s.replace('static std::atomic<int> vkKickMode{1};', 'static std::atomic<int> vkKickMode{5};', 1)

p.write_text(s, encoding='utf-8')
print('kick mode 5/6 added; default = 5')
