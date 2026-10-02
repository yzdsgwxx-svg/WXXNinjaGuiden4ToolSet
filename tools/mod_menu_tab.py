"""菜单里换页签（LB/RB）就存档。

用户观察：暂停菜单有 武器和装备 / 物品 / 忍务 / 系统 四个页签，LB/RB 切换；
"系统"页签里才有返回标题/退出游戏，所以切页签时存档 = 在玩家离开前精准落地。
实现：Worker 里用 XInput 只读轮询手柄，LB/RB 边沿触发（长按不重复），仅在菜单打开时生效。
定期补存保留作兜底（键盘切页签时用），默认间隔放宽到 5 秒。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) XInput 边沿检测
old = 'static void NoteSaveProgress(){'
assert old in s, 'anchor'
s = s.replace(old, '''/* 菜单页签键（手柄 LB/RB）：只读轮询，边沿触发。xinput 由我们按需加载。 */
static bool MenuTabPressed(){
    using GetState=DWORD(WINAPI*)(DWORD,void*);
    static GetState getState=nullptr;static bool tried=false;
    if(!tried){
        tried=true;
        HMODULE lib=LoadLibraryW(L"xinput1_4.dll");
        if(!lib)lib=LoadLibraryW(L"xinput1_3.dll");
        if(!lib)lib=LoadLibraryW(L"xinput9_1_0.dll");
        if(lib)getState=reinterpret_cast<GetState>(GetProcAddress(lib,"XInputGetState"));
        Log("XInput for menu tab detection: %s",getState?"ok":"unavailable");
    }
    if(!getState)return false;
    struct PadState{DWORD packet;struct{DWORD buttons;BYTE lt,rt;short lx,ly,rx,ry;}pad;};
    static DWORD previous[4]={0,0,0,0};
    bool edge=false;
    for(DWORD i=0;i<4;++i){
        PadState st{};
        const bool connected=getState(i,&st)==0;
        const DWORD tabs=connected?(st.pad.buttons&0x0300):0;      // 0x0100 LB, 0x0200 RB
        if((tabs&~previous[i])!=0)edge=true;                       // 新按下才算
        previous[i]=tabs;
    }
    return edge;
}
''' + old, 1)

# 2) Worker 菜单块里加页签触发
old = '''            }else if(armed&&now-lastMenuSave.load()>menuIntervalMs.load()){'''
assert old in s, 'periodic branch'
s = s.replace(old, '''            }else if(armed&&MenuTabPressed()){
                /* 玩家在菜单里换页签（LB/RB）——"系统"页签里才有返回标题/退出游戏，先存一次。 */
                KickGameSave("menu tab switch");
                lastMenuSave=now;
            }else if(armed&&now-lastMenuSave.load()>menuIntervalMs.load()){''', 1)

# 3) 补存间隔默认 3 秒 → 5 秒
s = s.replace('static std::atomic<unsigned> menuIntervalMs{3000};',
              'static std::atomic<unsigned> menuIntervalMs{5000};', 1)
s = s.replace('unsigned interval=GetPrivateProfileIntW(L"Save",L"MenuIntervalMs",3000,configPath);',
              'unsigned interval=GetPrivateProfileIntW(L"Save",L"MenuIntervalMs",5000,configPath);', 1)

p.write_text(s, encoding='utf-8')
print('menu tab (LB/RB) trigger added')
