from pathlib import Path

p = Path('src/launcher.cpp')
s = p.read_text(encoding='utf-8')

# Tighten the two lower cards: the overlay card held one row, the save card lost the sync row.
pairs = [
    ('RoundRect(dc,24,254,750,362,16,16);RoundRect(dc,24,376,750,500,16,16);',
     'RoundRect(dc,24,254,750,340,16,16);RoundRect(dc,24,354,750,484,16,16);'),
    ('Label(dc,48,261,L"控制器覆层",RGB(232,220,207),gTitleFont);\n        Label(dc,48,391,L"存档",RGB(232,220,207),gTitleFont);',
     'Label(dc,48,262,L"控制器覆层",RGB(232,220,207),gTitleFont);\n        Label(dc,48,362,L"存档",RGB(232,220,207),gTitleFont);'),
    ('gOverlayState=Add(w,L"STATIC",L"未打开",0,48,295,420,24,130);',
     'gOverlayState=Add(w,L"STATIC",L"未打开",0,48,296,420,24,130);'),
    ('Add(w,L"BUTTON",L"控制器覆层：关闭",0,600,268,126,36,ID_OVERLAY_OPEN);',
     'Add(w,L"BUTTON",L"控制器覆层：关闭",0,600,268,126,36,ID_OVERLAY_OPEN);'),
    ('gSaveState=Add(w,L"STATIC",L"",0,48,425,440,24,ID_SAVESTATE);',
     'gSaveState=Add(w,L"STATIC",L"",0,48,396,440,24,ID_SAVESTATE);'),
    ('Add(w,L"BUTTON",L"存档切换：开启",0,600,391,126,36,ID_SWITCH_TOGGLE);',
     'Add(w,L"BUTTON",L"存档切换：开启",0,600,362,126,36,ID_SWITCH_TOGGLE);'),
    ('CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,48,457,440,150,ID_PROFILE);',
     'CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,48,428,440,150,ID_PROFILE);'),
    ('Add(w,L"BUTTON",L"切换存档",0,506,454,110,38,ID_SWITCH);',
     'Add(w,L"BUTTON",L"切换存档",0,506,425,110,38,ID_SWITCH);'),
    ('Add(w,L"BUTTON",L"存档目录",0,628,454,98,38,ID_OPENSAVES+100);',
     'Add(w,L"BUTTON",L"存档目录",0,628,425,98,38,ID_OPENSAVES+100);'),
    ('Add(w,L"BUTTON",L"查看日志",0,654,524,96,32,ID_OPENSAVES);',
     'Add(w,L"BUTTON",L"查看日志",0,654,506,96,32,ID_OPENSAVES);'),
    ('work.top+(work.bottom-work.top-588)/2,774,588,nullptr',
     'work.top+(work.bottom-work.top-570)/2,774,570,nullptr'),
]
for old, new in pairs:
    assert old in s, old
    s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
print('layout tightened')
