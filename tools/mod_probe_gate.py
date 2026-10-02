"""把诊断日志收到 [Save] Probe 开关后面：正式版日志只留关键行，测试时打开即可。

- Probe=1（默认，测试用）：两秒一次的实例/阶段报告、每次 load 请求、阶段迁移、管理器构造/析构
- Probe=0（发布用）：只留 配置加载 / SAVE kick / SAVE skipped / 存档阶段结束 / 文件写盘
"""
from pathlib import Path

p = Path(r'D:\APP\WXXNinjaGuiden4ToolSet\src\mod.cpp')
s = p.read_text(encoding='utf-8')

# 1) 全局开关
old = 'static std::atomic<int> saveInFlight{0};   // 1 = 我们踢出去的存档阶段还没走完'
assert old in s
s = s.replace(old, old + '\nstatic std::atomic<int> probeVerbose{1};  // [Save] Probe：1=诊断日志全开', 1)

# 2) LoadConfig 读取
old = '    vkKickMode=kickMode;'
assert old in s
s = s.replace(old, old + '''
    probeVerbose=GetPrivateProfileIntW(L"Save",L"Probe",1,configPath)?1:0;''', 1)
old = '    Log("Save on exit: %s; manual test key 0x%02x",exitSave?"on":"off",testKey);'
assert old in s
s = s.replace(old, old + '\n    Log("Diagnostics: probe=%s kick mode=%d",probeVerbose.load()?"on":"off",kickMode);', 1)

# 3) 诊断日志加条件
gated = [
    ('    Log("PROBE %s this=%p caller=+0x%llx accepted=%d busy=%u code=%u slot=%u",tag,manager,',
     '    if(probeVerbose.load())Log("PROBE %s this=%p caller=+0x%llx accepted=%d busy=%u code=%u slot=%u",tag,manager,'),
    ('    Log("PROBE SAVE Slot slot=%d meta=%p caller=+0x%llx accepted=%d busy=%u code=%u",slot,meta,',
     '    if(probeVerbose.load())Log("PROBE SAVE Slot slot=%d meta=%p caller=+0x%llx accepted=%d busy=%u code=%u",slot,meta,'),
    ('    Log("PROBE REQ %s code=%d caller=+0x%llx manager_ok=%d updates=%u",tag,code,',
     '    if(probeVerbose.load())Log("PROBE REQ %s code=%d caller=+0x%llx manager_ok=%d updates=%u",tag,code,'),
    ('    Log("PROBE TRANS %s caller=+0x%llx updates=%u manager=%p ok=%d",tag,',
     '    if(probeVerbose.load())Log("PROBE TRANS %s caller=+0x%llx updates=%u manager=%p ok=%d",tag,'),
    ('    Log("PROBE instance=%p vtable=%p match=%d source=%d updates=%u",reinterpret_cast<void*>(m),',
     '    if(probeVerbose.load())Log("PROBE instance=%p vtable=%p match=%d source=%d updates=%u",reinterpret_cast<void*>(m),'),
    ('    Log("PROBE session=%p outer=%u sub=%u alive=%d",reinterpret_cast<void*>(session),outer,sub,int(SessionAlive()));',
     '    if(probeVerbose.load())Log("PROBE session=%p outer=%u sub=%u alive=%d",reinterpret_cast<void*>(session),outer,sub,int(SessionAlive()));'),
    ('        Log("PROBE stage %u -> %u",lastStage,stage);',
     '        if(probeVerbose.load())Log("PROBE stage %u -> %u",lastStage,stage);'),
    ('    Log("PROBE manager dtor this=%p flags=%d caller=+0x%llx",manager,flags,(unsigned long long)caller);',
     '    if(probeVerbose.load())Log("PROBE manager dtor this=%p flags=%d caller=+0x%llx",manager,flags,(unsigned long long)caller);'),
    ('    Log("PROBE session %s: %p -> %p",previous?"changed":"captured",',
     '    if(probeVerbose.load())Log("PROBE session %s: %p -> %p",previous?"changed":"captured",'),
]
for old_t, new_t in gated:
    assert old_t in s, old_t[:50]
    s = s.replace(old_t, new_t, 1)

# 4) 两秒报告整体受开关控制
old = '        if(now-lastProbe>2000){lastProbe=now;ProbeReport();}'
assert old in s
s = s.replace(old, '        if(probeVerbose.load()&&now-lastProbe>2000){lastProbe=now;ProbeReport();}', 1)

p.write_text(s, encoding='utf-8')
print('probe logging gated')
