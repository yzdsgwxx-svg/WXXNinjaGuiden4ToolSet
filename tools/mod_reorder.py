"""把"踢存档状态机"整块搬到 ProbeReport / SaveFlowHook 之前，修掉定义顺序。"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
lines = p.read_text(encoding='utf-8').split('\n')

def find(prefix, start=0):
    for i in range(start, len(lines)):
        if lines[i].startswith(prefix):
            return i
    raise SystemExit('not found: ' + prefix)

# 整块：从 "/* ==== 退出时存档：踢游戏自己的存档状态机" 到 WaitForPendingSave 结束
blk_start = None
for i, l in enumerate(lines):
    if l.startswith('/* ================= 退出时存档：踢游戏自己的存档状态机'):
        blk_start = i
        break
assert blk_start is not None
wait_start = find('static void WaitForPendingSave(const char* where){')
# 找块尾：WaitForPendingSave 的结束（下一个顶层 '}' 后跟空行）
j = wait_start
while lines[j] != '}':
    j += 1
blk_end = j + 1
block = lines[blk_start:blk_end]
assert any('kRvaSaveFlow' in l for l in block) and any('KickGameSave' in l for l in block)

# 删掉原位置
rest = lines[:blk_start] + lines[blk_end:]

# 插到 ProbeReport 之前
target = None
for i, l in enumerate(rest):
    if l.startswith('static void ProbeReport(){'):
        target = i
        break
assert target is not None
out = rest[:target] + block + [''] + rest[target:]

# SaveFlowHook 里用了 LogTransition（在它之后定义不了就先声明）——改成自己打日志，避免依赖
text = '\n'.join(out)
text = text.replace('    if(caller<0x100000)LogTransition("save flow",caller);\n', '')
old_hook = '''static void* __fastcall SaveFlowHook(void* session){
    const uintptr_t caller=CallerRva();
    if(!sessionObject.load()&&session)sessionObject=reinterpret_cast<uintptr_t>(session);
    void* result=saveFlowOriginal(session);
    return result;
}'''
new_hook = '''static void* __fastcall SaveFlowHook(void* session){
    const uintptr_t caller=CallerRva();
    const bool first=!sessionObject.load()&&session!=nullptr;
    if(first)sessionObject=reinterpret_cast<uintptr_t>(session);
    void* result=saveFlowOriginal(session);
    if(first)Log("PROBE session captured from save flow: %p",session);
    else Log("PROBE TRANS save flow caller=+0x%llx state=%u upstream=%u",(unsigned long long)caller,
        *reinterpret_cast<unsigned*>(uintptr_t(session)+kOffFlowState),flowStateBefore);
    return result;
}'''
assert old_hook in text
# 记录调用前状态
text = text.replace(old_hook, '''static void* __fastcall SaveFlowHook(void* session){
    const uintptr_t caller=CallerRva();
    unsigned flowStateBefore=0xffffffffu;
    __try{flowStateBefore=*reinterpret_cast<unsigned*>(uintptr_t(session)+kOffFlowState);}
    __except(EXCEPTION_EXECUTE_HANDLER){flowStateBefore=0xffffffffu;}
    const bool first=!sessionObject.load()&&session!=nullptr;
    if(first)sessionObject=reinterpret_cast<uintptr_t>(session);
    void* result=saveFlowOriginal(session);
    if(first)Log("PROBE session captured from save flow: %p",session);
    else Log("PROBE TRANS save flow caller=+0x%llx state=%u upstream=%u",(unsigned long long)caller,
        flowStateBefore,*reinterpret_cast<unsigned*>(uintptr_t(session)+kOffFlowState));
    return result;
}''', 1)

p.write_text(text, encoding='utf-8')
print('moved save-flow block before ProbeReport; lines', len(text.split(chr(10))))
