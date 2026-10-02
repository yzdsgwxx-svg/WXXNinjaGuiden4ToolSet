"""把触发点从旧的"自己拼请求序列"改成"踢游戏存档状态机"。"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

subs = [
    ('if(autoSaveOn.load())StartSaveSequence("back to title");',
     'if(autoSaveOn.load())KickGameSave("back to title");'),
    ('        if(now-lastSaveAt.load()>3)StartSaveSequence("session teardown");',
     '        if(now-lastSaveAt.load()>3)KickGameSave("session teardown");'),
    ('        AdvanceSaveSequence();\n', ''),
    ('            if(testKeyDown&&!lastTest)StartSaveSequence("manual test key");',
     '            if(testKeyDown&&!lastTest)kickRequest=now;'),
    ('''    /* 存档序列直接复用探针抓住的原函数指针。 */
    requestGameData=request7Original;
    systemData=request6Original;
    saveSlot=request8Original;
    Log("Save-on-exit entries: GameData=%p SystemData=%p SlotData=%p",
        reinterpret_cast<void*>(requestGameData),reinterpret_cast<void*>(systemData),reinterpret_cast<void*>(saveSlot));
''', ''),
    ('''static void ProbeReport(){
    const uintptr_t m=saveManager.load();''',
     '''static void ProbeReport(){
    const uintptr_t m=saveManager.load();
    const uintptr_t session=sessionObject.load();
    const unsigned flowState=SessionState();'''),
    ('        reinterpret_cast<void*>(vtable),int(match),saveManagerSource.load(),updates.load());',
     '        reinterpret_cast<void*>(vtable),int(match),saveManagerSource.load(),updates.load());\n'
     '    Log("PROBE session=%p flow_state=%u alive=%d",reinterpret_cast<void*>(session),flowState,int(SessionAlive()));'),
]
for old, new in subs:
    assert old in s, 'missing: ' + old[:60]
    s = s.replace(old, new, 1)

# UpdateHook：在游戏线程消费 F10 请求（状态机必须在游戏线程上踢）
hook_head = '''static void __fastcall UpdateHook(void* player){
    ++updates;
    NoteUpdateGap();'''
assert hook_head in s
s = s.replace(hook_head, hook_head + '''
    /* F10 手动验证：请求在 Worker 里置位，这里在游戏线程执行踢一脚。 */
    if(const ULONGLONG ticked=kickRequest.exchange(0)){
        if(GetTickCount64()-ticked<1500&&enabled.load(std::memory_order_relaxed))KickGameSave("manual test key");
    }''', 1)

# Install()：挂存档状态机 hook（登录 session 用），取代已删除的请求入口转发
old_install = '''    const ProbeHook probe2[]={
        {"load2",0x102de10,q2,sizeof q2,reinterpret_cast<void*>(&Load2Hook),reinterpret_cast<void**>(&load2Original)},'''
new_install = '''    static const unsigned char qf[]={0x4c,0x8b,0xdc,0x49,0x89,0x7b,0x20,0x55,0x49,0x8d,0xab,0xa8,0xfb,0xff,0xff,0x48};
    const ProbeHook probe2[]={
        {"save flow",0xc460b0,qf,sizeof qf,reinterpret_cast<void*>(&SaveFlowHook),reinterpret_cast<void**>(&saveFlowOriginal)},
        {"load2",0x102de10,q2,sizeof q2,reinterpret_cast<void*>(&Load2Hook),reinterpret_cast<void**>(&load2Original)},'''
assert old_install in s
s = s.replace(old_install, new_install, 1)

# 状态机 hook 实体：捕获 session
anchor = 'static bool __fastcall Load2Hook(void* manager,void* slot,void* meta){'
assert anchor in s
s = s.replace(anchor, '''static void* __fastcall SaveFlowHook(void* session){
    const uintptr_t caller=CallerRva();
    if(!sessionObject.load()&&session)sessionObject=reinterpret_cast<uintptr_t>(session);
    void* result=saveFlowOriginal(session);
    if(caller<0x100000)LogTransition("save flow",caller);
    return result;
}
''' + anchor, 1)

p.write_text(s, encoding='utf-8')
print('mod.cpp rewired')
