"""修刷屏：菜单检测每 4 ms 触发一次，去重日志跟着刷（实测几分钟 786 KB）。

改成闩锁：进入菜单时只踢一次，玩家 update 恢复后再解除闩锁。
另外给"被去重拦住"的日志加 2 秒限流兜底。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 闩锁
old = 'static std::atomic<ULONGLONG> saveWaitDone{0};    // 上一次等存档结束的时刻（避免连环等）'
assert old in s, 'wait atomic'
s = s.replace(old, old + '\nstatic std::atomic<int> menuLatch{0};            // 1 = 本次进入菜单已经存过了',
              1)
old = 'static std::atomic<ULONGLONG> lastSkipLog{0};'
if old not in s:
    s = s.replace('static std::atomic<int> menuLatch{0};            // 1 = 本次进入菜单已经存过了',
                  'static std::atomic<int> menuLatch{0};            // 1 = 本次进入菜单已经存过了\n'
                  'static std::atomic<ULONGLONG> lastSkipLog{0};    // 去重日志限流', 1)

# 2) Worker 里的菜单检测改成闩锁
old = '''        if(autoSaveOn.load()&&saveOnPause.load()&&sessionObject.load()&&
           SessionStage()==kIdleStage&&lastPlayerTick.load()&&
           now-lastPlayerTick.load()>1500){
            KickGameSave("menu opened");
        }'''
assert old in s, 'menu block'
new = '''        const bool menuOpen=sessionObject.load()&&SessionStage()==kIdleStage&&lastPlayerTick.load()&&
            now-lastPlayerTick.load()>1500;
        if(menuOpen){
            if(!menuLatch.exchange(1)&&autoSaveOn.load()&&saveOnPause.load())KickGameSave("menu opened");
        }else menuLatch=0;'''
s = s.replace(old, new, 1)

# 3) 去重日志限流（2 秒）
old = '    if(previous&&now-previous<20){Log("SAVE skipped (%s): last kick was %d s ago",reason,now-previous);return;}'
assert old in s, 'dedupe'
s = s.replace(old, '''    if(previous&&now-previous<20){
        const ULONGLONG stamp=GetTickCount64();
        if(stamp-lastSkipLog.load()>2000){lastSkipLog=stamp;Log("SAVE skipped (%s): last kick was %d s ago",reason,now-previous);}
        return;
    }''', 1)

p.write_text(s, encoding='utf-8')
print('menu latch + log throttle added')
