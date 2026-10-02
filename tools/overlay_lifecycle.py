from pathlib import Path
p=Path('overlay/main.js');s=p.read_text(encoding='utf-8').replace("app.on('second-instance', () => { log('second-instance'); showWindow(); });", "app.on('second-instance', (_event, argv) => { if (argv.includes('--close')) app.quit(); else showWindow(); });")
s=s.replace("  app.whenReady()", "  if (process.argv.includes('--close')) app.quit();\n  else app.whenReady()")
s=s.replace("    const result = rumbleSource.injectDll(target, rumbleDll);", "    if (rumbleInfo.injectedPid && rumbleInfo.injectedPid !== target) rumbleSource.setEnabled(rumbleInfo.injectedPid, false);\n    const result = rumbleSource.injectDll(target, rumbleDll);\n    if (result.ok) rumbleSource.selectTarget(target);")
s=s.replace("  const rumbleInfo = { injectedPid: 0, message: rumbleError || '未注入' };", "  const rumbleInfo = { injectedPid: 0, message: rumbleError || '未注入' };\n  app.on('before-quit', () => { if (rumbleSource && rumbleInfo.injectedPid) rumbleSource.setEnabled(rumbleInfo.injectedPid, false); });")
p.write_text(s,encoding='utf-8')
p=Path('overlay/rumble-source.js');s=p.read_text(encoding='utf-8').replace('    koffi,','    koffi, kernel32, psapi,\n    OpenEventW: kernel32.func(\'uintptr_t __stdcall OpenEventW(uint32_t access, bool inherit, const char16_t *name)\'),\n    SetEvent: kernel32.func(\'bool __stdcall SetEvent(uintptr_t handle)\'),')
s=s.replace('let mapping = 0, view = 0, nextRetry = 0;', 'let mapping = 0, view = 0, nextRetry = 0, targetPid = 0;\nfunction selectTarget(pid) { closeView(); targetPid = pid; nextRetry = 0; setEnabled(pid, true); }\nfunction setEnabled(pid, enabled) {\n  if (!api || !pid) return false;\n  const event = api.OpenEventW(2, false, `Local\\\\WXXRumble_${enabled ? "Start" : "Stop"}_${pid}`);\n  if (!event) return false;\n  try { return api.SetEvent(event); } finally { api.CloseHandle(event); }\n}')
s=s.replace('false, SHARED_NAME)', "false, targetPid ? `${SHARED_NAME}_${targetPid}` : SHARED_NAME)")
s=s.replace("  if (!api) return { ok: false, error: 'koffi 不可用：' + loadError };", "  if (!api) return { ok: false, error: 'koffi 不可用：' + loadError };\n  if (setEnabled(pid, true)) return { ok:true, pid };")
s=s.replace('let remote = 0, thread = 0;', 'let remote = 0, thread = 0, threadFinished = false;')
s=s.replace('    const exitCode = [0];','    threadFinished = true;\n    const exitCode = [0];')
s=s.replace('if (remote) api.VirtualFreeEx', 'if (remote && (!thread || threadFinished)) api.VirtualFreeEx')
s=s.replace('module.exports = {', 'module.exports = { selectTarget, setEnabled,')
p.write_text(s,encoding='utf-8')
p=Path('overlay/native/rumble-hook/rumble_hook.cpp');s=p.read_text(encoding='utf-8').replace('#include <stdint.h>','#include <stdint.h>\n#include <cwchar>')
s=s.replace('    g_mapping = CreateFileMappingW', '    wchar_t sharedName[128];\n    swprintf_s(sharedName,L"%s_%lu",RUMBLE_SHARED_NAME,GetCurrentProcessId());\n    g_mapping = CreateFileMappingW').replace('sizeof(RumbleShared), RUMBLE_SHARED_NAME)', 'sizeof(RumbleShared), sharedName)')
s=s.replace('    for (;;) {\n        TryHookAll();\n        Sleep(500);\n    }', '''    wchar_t stopName[96], startName[96];
    swprintf_s(stopName,L"Local\\\\WXXRumble_Stop_%lu",GetCurrentProcessId());
    swprintf_s(startName,L"Local\\\\WXXRumble_Start_%lu",GetCurrentProcessId());
    HANDLE stop=CreateEventW(nullptr,FALSE,FALSE,stopName),start=CreateEventW(nullptr,FALSE,FALSE,startName);
    bool active=true;
    for (;;) {
        if(stop && WaitForSingleObject(stop,0)==WAIT_OBJECT_0){
            active=false;
            for(auto target:g_target)if(target)MH_DisableHook(target);
            if(g_shared){g_shared->strength=0;g_shared->hookedCount=0;}
        }
        if(start && WaitForSingleObject(start,0)==WAIT_OBJECT_0){
            active=true;
            for(auto target:g_target)if(target)MH_EnableHook(target);
            if(g_shared)g_shared->hookedCount=g_hooked;
        }
        if(active)TryHookAll();
        Sleep(100);
    }''')
p.write_text(s,encoding='utf-8')
p=Path('overlay/native/rumble-hook/build.bat');s=p.read_text().replace('..\\third_party\\minhook-1.3.4','..\\..\\..\\third_party\\minhook');p.write_text(s,encoding='ascii')
