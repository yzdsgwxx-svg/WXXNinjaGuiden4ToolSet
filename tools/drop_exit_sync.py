from pathlib import Path

p = Path('src/launcher.cpp')
s = p.read_text(encoding='utf-8')
before = s

# --- 1. drop the exit-sync feature (state, ids, timer, command, ini) ---
s = s.replace(
    '/* 自动存档：游戏自己写存档（退出游戏 / 回标题 / 游戏中保存）之后留一份快照。 */\n'
    'static bool gAutoSave=true,gGameWasRunning=false;\n'
    'static std::wstring gSaveSig;\n',
    '/* 存档同步只在切换存档时进行：切换前把游戏当前存档写回当前档案。 */\n')
assert 'gAutoSave' not in s.split('static ULONGLONG gExitPending')[0]
s = s.replace('#define ID_AUTOSAVE 112\n', '')
s = s.replace('#define ID_SAVEGAME 113\n', '')
s = s.replace('static ULONGLONG gExitPending=0;\n', '')
s = s.replace('    gSaveSig=SaveSignature(); /* 面板自己改的存档不算游戏存档，刷新基线 */\n', '')
s = s.replace('RefreshAll();gSaveSig=SaveSignature();gGameWasRunning=FindGame()!=0;', 'RefreshAll();')

# --- 2. save card layout: rename button, drop the sync row, keep the card tight ---
s = s.replace(
    '        Add(w,L"BUTTON",L"档案目录",0,628,454,98,38,ID_OPENSAVES+100);\n'
    '        Add(w,L"STATIC",L"退出同步",0,48,522,90,24,132);\n'
    '        Add(w,L"BUTTON",gAutoSave?L"退出同步：开启":L"退出同步：关闭",0,600,514,126,36,ID_AUTOSAVE);\n'
    '        Add(w,L"BUTTON",L"查看日志",0,630,590,96,32,ID_OPENSAVES);\n',
    '        Add(w,L"BUTTON",L"存档目录",0,628,454,98,38,ID_OPENSAVES+100);\n'
    '        Add(w,L"BUTTON",L"查看日志",0,654,524,96,32,ID_OPENSAVES);\n')
s = s.replace(
    'RoundRect(dc,24,88,750,232,16,16);RoundRect(dc,24,246,750,354,16,16);RoundRect(dc,24,368,750,568,16,16);',
    'RoundRect(dc,24,88,750,240,16,16);RoundRect(dc,24,254,750,362,16,16);RoundRect(dc,24,376,750,500,16,16);')
s = s.replace(
    '        Label(dc,48,103,L"六槽武器",RGB(232,220,207),gTitleFont);\n'
    '        Label(dc,48,253,L"控制器覆层",RGB(232,220,207),gTitleFont);\n'
    '        Label(dc,48,383,L"存档",RGB(232,220,207),gTitleFont);\n'
    '        Label(dc,158,522,L"同步游戏已写盘的进度",RGB(150,139,142),gFont);\n'
    '        Label(dc,48,596,L"WXX  /  忍龙 4 工具集",RGB(135,125,126),gFont);\n',
    '        Label(dc,48,103,L"六槽武器",RGB(232,220,207),gTitleFont);\n'
    '        Label(dc,48,261,L"控制器覆层",RGB(232,220,207),gTitleFont);\n'
    '        Label(dc,48,391,L"存档",RGB(232,220,207),gTitleFont);\n')

# --- 3. move the two lower cards' children to the new card rows ---
s = s.replace('gModState=Add(w,L"STATIC",L"",0,48,137,420,24,ID_MODSTATE);',
              'gModState=Add(w,L"STATIC",L"",0,48,145,420,24,ID_MODSTATE);')
s = s.replace('Add(w,L"BUTTON",L"六槽武器：关闭",0,600,105,126,36,ID_MOD_LOAD);',
              'Add(w,L"BUTTON",L"六槽武器：关闭",0,600,113,126,36,ID_MOD_LOAD);')
s = s.replace('Add(w,L"BUTTON",L"6槽武器设置",0,48,178,180,38,ID_CONFIG);',
              'Add(w,L"BUTTON",L"6槽武器设置",0,48,186,180,38,ID_CONFIG);')
s = s.replace('gOverlayState=Add(w,L"STATIC",L"未打开",0,48,287,420,24,130);',
              'gOverlayState=Add(w,L"STATIC",L"未打开",0,48,295,420,24,130);')
s = s.replace('Add(w,L"BUTTON",L"控制器覆层：关闭",0,600,260,126,36,ID_OVERLAY_OPEN);',
              'Add(w,L"BUTTON",L"控制器覆层：关闭",0,600,268,126,36,ID_OVERLAY_OPEN);')
s = s.replace('gSaveState=Add(w,L"STATIC",L"",0,48,417,460,24,ID_SAVESTATE);',
              'gSaveState=Add(w,L"STATIC",L"",0,48,425,440,24,ID_SAVESTATE);')
s = s.replace('Add(w,L"BUTTON",L"存档切换：开启",0,600,383,126,36,ID_SWITCH_TOGGLE);',
              'Add(w,L"BUTTON",L"存档切换：开启",0,600,391,126,36,ID_SWITCH_TOGGLE);')
s = s.replace('CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,48,457,440,140,ID_PROFILE);',
              'CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,48,457,440,150,ID_PROFILE);')

# --- 4. stop treating the removed switch as a capsule control ---
s = s.replace('if(d->CtlID==ID_MOD_LOAD||d->CtlID==ID_OVERLAY_OPEN||d->CtlID==ID_SWITCH_TOGGLE||d->CtlID==ID_AUTOSAVE){',
              'if(d->CtlID==ID_MOD_LOAD||d->CtlID==ID_OVERLAY_OPEN||d->CtlID==ID_SWITCH_TOGGLE){')
s = s.replace('bool on=d->CtlID==ID_MOD_LOAD?gWeaponOn:d->CtlID==ID_OVERLAY_OPEN?gOverlayOn:d->CtlID==ID_SWITCH_TOGGLE?gSwitchEnabled:gAutoSave;',
              'bool on=d->CtlID==ID_MOD_LOAD?gWeaponOn:d->CtlID==ID_OVERLAY_OPEN?gOverlayOn:gSwitchEnabled;')

# --- 5. timer no longer schedules a snapshot after the game exits ---
s = s.replace(
    '        if(gGameWasRunning&&!running&&gAutoSave)gExitPending=GetTickCount64()+1500;\n'
    '        gGameWasRunning=running;\n'
    '        if(gExitPending&&GetTickCount64()>=gExitPending){\n'
    '            gExitPending=0;if(!running&&gAutoSave)SyncCurrentProfile();\n'
    '        }return 0;\n',
    '        return 0;\n')

# --- 6. drop the command handler and the ini key ---
s = s.replace(
    '        case ID_AUTOSAVE:\n'
    '            gAutoSave=!gAutoSave;gExitPending=0;SetWindowTextW(GetDlgItem(w,ID_AUTOSAVE),gAutoSave?L"退出同步：开启":L"退出同步：关闭");\n'
    '            WritePrivateProfileStringW(L"Toolset",L"ExitSync",gAutoSave?L"1":L"0",Join(gExeDir,L"SixSlot.ini").c_str());return 0;\n', '')
s = s.replace('    gAutoSave=GetPrivateProfileIntW(L"Toolset",L"ExitSync",1,Join(gExeDir,L"SixSlot.ini").c_str())!=0;\n', '')

# --- 7. window is shorter now that the save card lost a row ---
s = s.replace('work.top+(work.bottom-work.top-648)/2,774,648,nullptr', 'work.top+(work.bottom-work.top-588)/2,774,588,nullptr')

for token in ('gAutoSave', 'gExitPending', 'gGameWasRunning', 'gSaveSig', 'ID_AUTOSAVE', 'ExitSync', '档案目录'):
    assert token not in s, token
assert '存档目录' in s and 'SyncCurrentProfile' in s
p.write_text(s, encoding='utf-8')
print('launcher.cpp updated, delta bytes:', len(before) - len(s))
