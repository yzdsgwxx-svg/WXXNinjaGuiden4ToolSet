"""安全闸：只在会话处于空闲阶段（1）时才踢存档。

之前只检查了子状态 [0x100]，但真正重要的是外层阶段：如果玩家在读档/存档途中触发，
直接切到阶段 3 会打断游戏自己的流程。改成检查 [0xf0]==1。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

old = '''    const unsigned state=SessionState();
    if(state!=0){Log("SAVE skipped (%s): save flow busy (state %u)",reason,state);return;}'''
assert old in s
new = '''    const unsigned stage=SessionStage();
    if(stage!=kIdleStage){Log("SAVE skipped (%s): stage %u busy (idle=%u)",reason,stage,kIdleStage);return;}'''
s = s.replace(old, new, 1)

# 日志里原先引用 state 的地方改成 stage
old = '''    Log("SAVE kick mode=%d: %s (session=%p outer=%u sub=%u)",mode,reason,reinterpret_cast<void*>(session),outer,state);'''
assert old in s
s = s.replace(old, '''    Log("SAVE kick mode=%d: %s (session=%p outer=%u sub=%u)",mode,reason,reinterpret_cast<void*>(session),outer,SessionState());''', 1)

p.write_text(s, encoding='utf-8')
print('idle-stage guard added')
