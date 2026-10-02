"""阶段变化打点：摸清"返回标题/退出游戏"在外层阶段机上分别走哪一步。

存档阶段已确认：3（GameData+SystemData）→ 5（SlotData+GameData）→ 回 1。
退出路径还没测过，先把阶段迁移记下来，再决定挂哪一层。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

old = '''    sessionUpdateOriginal(session);
    return nullptr;
}'''
assert old in s
new = '''    /* 阶段迁移打点：存档 3→5→1 已确认，退出/回标题走哪一步还没测过。 */
    static unsigned lastStage=0xffffffffu;
    const unsigned stage=SessionStage();
    if(stage!=lastStage&&stage!=0xffffffffu){
        Log("PROBE stage %u -> %u",lastStage,stage);
        lastStage=stage;
    }
    sessionUpdateOriginal(session);
    return nullptr;
}'''
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('stage transition logging added')
