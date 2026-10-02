"""把"菜单检测"从会话 update 挪到 Worker：
会话 update 在菜单里是否还跑没法保证；Worker 是我们自己的线程，永远在跑。
判据不变：玩家 update 停了 + 会话仍是空闲阶段 = 人在菜单里。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

old = '''    /* 菜单检测：玩家 update 停了、会话仍是空闲阶段 → 人在菜单里（读档时阶段非空闲，天然排除）。
       两个"离开"动作都先拆会话，等到那一刻再存已经来不及，所以在这里先存一次。 */
    if(autoSaveOn.load()&&saveOnPause.load()&&SessionStage()==kIdleStage&&lastPlayerTick.load()){
        const ULONGLONG now=GetTickCount64();
        if(now-lastPlayerTick.load()>1500)KickGameSave("menu opened");
    }
'''
assert old in s, 'menu block in session update'
s = s.replace(old, '', 1)

old = '        NoteSaveProgress();'
assert old in s, 'worker hook point'
s = s.replace(old, '''        /* 菜单检测：玩家 update 停了、会话仍是空闲阶段 → 人在菜单里（读档/存档时阶段非空闲，天然排除）。
           两个"离开"动作都先拆会话，等到那一刻再存已经来不及，所以在菜单一打开就存一次。
           放在 Worker 里做，不依赖游戏在菜单里是否还跑会话 update。 */
        if(autoSaveOn.load()&&saveOnPause.load()&&sessionObject.load()&&
           SessionStage()==kIdleStage&&lastPlayerTick.load()&&
           now-lastPlayerTick.load()>1500){
            KickGameSave("menu opened");
        }
        NoteSaveProgress();''', 1)

p.write_text(s, encoding='utf-8')
print('menu detection moved to worker')
