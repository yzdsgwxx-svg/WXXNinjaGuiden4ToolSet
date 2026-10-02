"""去掉"菜单里定时补存"——用户实测反馈：每 3 秒一次太吵，游戏里能看到一直在存档。

只留精准触发：① 进菜单存一次 ② 切页签（LB/RB）存一次。
MenuIntervalMs 改成默认 0 = 关闭；允许设 0（原来被夹到最小 1000，关不掉）。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 默认关闭
s = s.replace('static std::atomic<unsigned> menuIntervalMs{5000};',
              'static std::atomic<unsigned> menuIntervalMs{0};   // 0 = 不做定时补存（用户要求：只在精准时机存）', 1)
s = s.replace('unsigned interval=GetPrivateProfileIntW(L"Save",L"MenuIntervalMs",5000,configPath);',
              'unsigned interval=GetPrivateProfileIntW(L"Save",L"MenuIntervalMs",0,configPath);', 1)
old = '    if(interval<1000)interval=1000;if(interval>60000)interval=60000;'
assert old in s, 'clamp'
s = s.replace(old, '    if(interval>60000)interval=60000;   // 0 = 关闭定时补存', 1)

# 2) 定时分支加 interval>0 条件；日志说明关闭状态
old = '            }else if(armed&&now-lastMenuSave.load()>menuIntervalMs.load()){'
assert old in s, 'periodic branch'
s = s.replace(old, '            }else if(armed&&menuIntervalMs.load()>0&&now-lastMenuSave.load()>menuIntervalMs.load()){', 1)
old = '    Log("Menu re-save interval: %u ms",menuIntervalMs.load());'
assert old in s, 'interval log'
s = s.replace(old, '    Log("Menu re-save interval: %s",menuIntervalMs.load()?std::to_string(menuIntervalMs.load()).append(" ms").c_str():"off (precise triggers only)");', 1)

p.write_text(s, encoding='utf-8')
print('periodic re-save removed (default off)')
