"""补菜单里"后续操作"的漏存：

闩锁只保证"每次进菜单存一次"，但玩家可以在菜单里换装备等，然后不关菜单直接离开 →
那次变更漏存（用户实测发现）。改成：进菜单立刻存一次，之后在菜单里按间隔补存。

- [Save] MenuIntervalMs 默认 3000
- 去重窗口从 20 秒降到 2 秒（否则会挡住补存）
- 补存不与进行中的存档重叠（看 saveInFlight）
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 间隔配置
old = 'static std::atomic<ULONGLONG> lastSkipLog{0};    // 去重日志限流'
assert old in s, 'skip log'
s = s.replace(old, old + '''
static std::atomic<ULONGLONG> lastMenuSave{0};   // 菜单里上一次存档的时刻
static std::atomic<unsigned> menuIntervalMs{3000};''', 1)

old = '    saveOnPause=GetPrivateProfileIntW(L"Save",L"SaveOnPause",1,configPath)?1:0;'
assert old in s, 'saveonpause read'
s = s.replace(old, old + '''
    unsigned interval=GetPrivateProfileIntW(L"Save",L"MenuIntervalMs",3000,configPath);
    if(interval<1000)interval=1000;if(interval>60000)interval=60000;
    menuIntervalMs=interval;''', 1)
old = '    Log("Save on pause menu: %s",saveOnPause.load()?"on":"off");'
assert old in s, 'pause log'
s = s.replace(old, old + '\n    Log("Menu re-save interval: %u ms",menuIntervalMs.load());', 1)

# 2) 菜单里定时补存
old = '''        if(menuOpen){
            if(!menuLatch.exchange(1)&&autoSaveOn.load()&&saveOnPause.load())KickGameSave("menu opened");
        }else menuLatch=0;'''
assert old in s, 'latch block'
new = '''        if(menuOpen){
            const bool armed=autoSaveOn.load()&&saveOnPause.load()&&!saveInFlight.load();
            if(!menuLatch.exchange(1)){
                if(armed){KickGameSave("menu opened");lastMenuSave=now;}
            }else if(armed&&now-lastMenuSave.load()>menuIntervalMs.load()){
                /* 菜单里待着：玩家可能在菜单里换了装备/改了设置，按间隔补存，避免不关菜单直接离开时漏掉。 */
                KickGameSave("menu open, periodic");
                lastMenuSave=now;
            }
        }else menuLatch=0;'''
s = s.replace(old, new, 1)

# 3) 去重窗口 20 秒 → 2 秒
old = '    if(previous&&now-previous<20){'
assert old in s, 'dedupe'
s = s.replace(old, '    if(previous&&now-previous<2){', 1)

p.write_text(s, encoding='utf-8')
print('menu periodic re-save added')
