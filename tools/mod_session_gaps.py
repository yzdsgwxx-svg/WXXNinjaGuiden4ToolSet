"""补齐两处缺口：
1) 会话换新要跟着换（回标题再进关卡会新建会话）；
2) 管理器直接从会话链 [session+0xe8] → holder → *holder 取，不再依赖 load/save 请求 hook。
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 从会话链里取管理器的小工具
anchor = 'static void* __fastcall SessionUpdateHook(void* session){'
assert anchor in s
s = s.replace(anchor, '''/* 会话 +0xe8 是"管理器 holder"，*holder 才是管理器：注入晚于读档时靠它补上实例。 */
static uintptr_t ManagerFromSession(uintptr_t session){
    if(!session)return 0;
    uintptr_t holder=0,manager=0;
    __try{
        holder=*reinterpret_cast<const uintptr_t*>(session+kOffManagerHolder);
        if(holder)manager=*reinterpret_cast<const uintptr_t*>(holder);
    }__except(EXCEPTION_EXECUTE_HANDLER){return 0;}
    return manager;
}
''' + anchor, 1)

# 2) 会话捕获：换新 + 顺手补管理器
old = '''static void* __fastcall SessionUpdateHook(void* session){
    const uintptr_t candidate=reinterpret_cast<uintptr_t>(session);
    if(candidate&&!sessionObject.load()&&ValidSession(candidate)){
        sessionObject=candidate;
        Log("PROBE session captured from session update: %p",session);
    }
    sessionUpdateOriginal(session);
    return nullptr;
}'''
assert old in s
new = '''static void* __fastcall SessionUpdateHook(void* session){
    const uintptr_t candidate=reinterpret_cast<uintptr_t>(session);
    if(candidate&&candidate!=sessionObject.load()&&ValidSession(candidate)){
        const uintptr_t previous=sessionObject.exchange(candidate);
        Log("PROBE session %s: %p -> %p",previous?"changed":"captured",
            reinterpret_cast<void*>(previous),reinterpret_cast<void*>(candidate));
        const uintptr_t manager=ManagerFromSession(candidate);
        if(manager&&saveManager.load()!=manager){
            saveManager=manager;saveManagerSource=4;
            Log("PROBE instance captured from session chain: %p",reinterpret_cast<void*>(manager));
        }
    }
    sessionUpdateOriginal(session);
    return nullptr;
}'''
s = s.replace(old, new, 1)

# 3) KickGameSave 用结构校验，不再要求"管理器早就已知"
old = '    if(!SessionAlive()){Log("SAVE skipped (%s): session/manager mismatch",reason);return;}'
assert old in s
s = s.replace(old, '''    if(!ValidSession(session)){Log("SAVE skipped (%s): session invalid (or manager mismatch)",reason);return;}
    const uintptr_t manager=ManagerFromSession(session);
    if(manager&&saveManager.load()!=manager){
        saveManager=manager;saveManagerSource=4;
        Log("SAVE: instance taken from session chain: %p",reinterpret_cast<void*>(manager));
    }''', 1)

p.write_text(s, encoding='utf-8')
print('gaps patched')
