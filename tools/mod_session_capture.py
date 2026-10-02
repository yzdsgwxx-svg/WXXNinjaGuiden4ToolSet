"""加"会话分发器"捕获点：0xc44980 每帧调用、rcx 就是会话对象。

比只靠存档状态机（0xc460b0）稳：注入晚于读档时，不必等游戏下一次存档就能拿到 session。
capture 时做结构校验：session+0xe8 → holder → manager → vtable 必须是 base+0x2262d10。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 类型 + 原函数指针 + 捕获函数，插在 SaveFlowHook 之前
anchor = 'static void* __fastcall SaveFlowHook(void* session){'
assert anchor in s
added = '''using SessionUpdate=void(__fastcall*)(void*);
static SessionUpdate sessionUpdateOriginal;
/* session+0xe8 是"管理器 holder"，*holder 才是管理器；用 vtable 做结构校验。 */
static bool ValidSession(uintptr_t session){
    if(!session)return false;
    uintptr_t holder=0,manager=0,vtable=0;
    __try{
        holder=*reinterpret_cast<const uintptr_t*>(session+kOffManagerHolder);
        if(holder)manager=*reinterpret_cast<const uintptr_t*>(holder);
        if(manager)vtable=*reinterpret_cast<const uintptr_t*>(manager);
    }__except(EXCEPTION_EXECUTE_HANDLER){return false;}
    if(vtable!=base+kVtableSaveManager)return false;
    const uintptr_t known=saveManager.load();
    return !known||known==manager;
}
/* 会话分发器每帧都会被调用，入口 rcx 就是会话对象：注入晚于读档也能立刻拿到。 */
static void* __fastcall SessionUpdateHook(void* session){
    const uintptr_t candidate=reinterpret_cast<uintptr_t>(session);
    if(candidate&&!sessionObject.load()&&ValidSession(candidate)){
        sessionObject=candidate;
        Log("PROBE session captured from session update: %p",session);
    }
    sessionUpdateOriginal(session);
    return nullptr;
}
''' + anchor
s = s.replace(anchor, added, 1)

# 2) Install()：注册这个 hook（放在 save flow 前面）
old = '''    static const unsigned char qf[]={0x4c,0x8b,0xdc,0x49,0x89,0x7b,0x20,0x55,0x49,0x8d,0xab,0xa8,0xfb,0xff,0xff,0x48};
    const ProbeHook probe2[]={
        {"save flow",0xc460b0,qf,sizeof qf,reinterpret_cast<void*>(&SaveFlowHook),reinterpret_cast<void**>(&saveFlowOriginal)},'''
new = '''    static const unsigned char qf[]={0x4c,0x8b,0xdc,0x49,0x89,0x7b,0x20,0x55,0x49,0x8d,0xab,0xa8,0xfb,0xff,0xff,0x48};
    static const unsigned char qs2[]={0x48,0x89,0x5c,0x24,0x10,0x48,0x89,0x74,0x24,0x18,0x48,0x89,0x7c,0x24,0x20,0x55};
    const ProbeHook probe2[]={
        {"session update",0xc44980,qs2,sizeof qs2,reinterpret_cast<void*>(&SessionUpdateHook),reinterpret_cast<void**>(&sessionUpdateOriginal)},
        {"save flow",0xc460b0,qf,sizeof qf,reinterpret_cast<void*>(&SaveFlowHook),reinterpret_cast<void**>(&saveFlowOriginal)},'''
assert old in s
s = s.replace(old, new, 1)

# 3) KillGameSave 报错信息更明确
s = s.replace('if(!session){Log("SAVE skipped (%s): session not captured yet",reason);return;}',
              'if(!session){Log("SAVE skipped (%s): session not captured yet (enter a level first)",reason);return;}', 1)

p.write_text(s, encoding='utf-8')
print('session-update capture added')
