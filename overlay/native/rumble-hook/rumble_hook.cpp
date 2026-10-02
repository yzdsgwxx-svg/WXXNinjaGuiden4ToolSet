/* RumbleHook.dll
   注入目标游戏进程后，hook 各版本 xinput*.dll 的 XInputSetState，
   把游戏写入的左右马达强度记录到共享内存，然后原样转发给真正的实现。
   只做记录与转发，不改变游戏行为、不修改窗口、不联网。 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <xinput.h>
#include <stdint.h>
#include <cwchar>
#include "shared.h"
#include "MinHook.h"

typedef DWORD (WINAPI *XInputSetStateFn)(DWORD dwUserIndex, XINPUT_VIBRATION* pVibration);
typedef DWORD (WINAPI *XInputGetStateFn)(DWORD dwUserIndex, XINPUT_STATE* pState);

static HANDLE           g_mapping = nullptr;
static RumbleShared*    g_shared  = nullptr;
static XInputSetStateFn g_orig[4] = { nullptr, nullptr, nullptr, nullptr };
static void*            g_target[4] = { nullptr, nullptr, nullptr, nullptr };
static const wchar_t*   g_modules[4] = { L"xinput1_4.dll", L"xinput1_3.dll", L"xinput1_2.dll", L"xinput1_1.dll" };
static volatile LONG    g_hooked = 0;

static void CreateShared() {
    wchar_t sharedName[128];
    swprintf_s(sharedName,L"%s_%lu",RUMBLE_SHARED_NAME,GetCurrentProcessId());
    g_mapping = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, sizeof(RumbleShared), sharedName);
    if (!g_mapping) return;
    g_shared = (RumbleShared*)MapViewOfFile(g_mapping, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(RumbleShared));
    if (!g_shared) return;
    g_shared->magic = RUMBLE_SHARED_MAGIC;
    g_shared->version = RUMBLE_SHARED_VERSION;
    g_shared->pid = GetCurrentProcessId();
    g_shared->tickMs = GetTickCount64();
}

/* 被 hook 的调用会高频进入这里，只允许做无锁内存写，不能有文件/日志/同步 IO。 */
static void ReportRumble(DWORD userIndex, const XINPUT_VIBRATION* vibration) {
    if (!g_shared) return;
    float left = 0.0f, right = 0.0f;
    if (vibration) {
        left  = (float)vibration->wLeftMotorSpeed  / 65535.0f;
        right = (float)vibration->wRightMotorSpeed / 65535.0f;
    }
    g_shared->userIndex = userIndex;
    g_shared->left = left;
    g_shared->right = right;
    g_shared->strength = (left > right) ? left : right;
    g_shared->tickMs = GetTickCount64();
    InterlockedIncrement64((volatile LONG64*)&g_shared->writeCount);
    InterlockedIncrement((volatile LONG*)&g_shared->seq);
}

#define HOOK_BODY(SLOT) \
    ReportRumble(dwUserIndex, pVibration); \
    return g_orig[SLOT] ? g_orig[SLOT](dwUserIndex, pVibration) : ERROR_DEVICE_NOT_CONNECTED;

static DWORD WINAPI Hook0(DWORD dwUserIndex, XINPUT_VIBRATION* pVibration) { HOOK_BODY(0) }
static DWORD WINAPI Hook1(DWORD dwUserIndex, XINPUT_VIBRATION* pVibration) { HOOK_BODY(1) }
static DWORD WINAPI Hook2(DWORD dwUserIndex, XINPUT_VIBRATION* pVibration) { HOOK_BODY(2) }
static DWORD WINAPI Hook3(DWORD dwUserIndex, XINPUT_VIBRATION* pVibration) { HOOK_BODY(3) }

static void* DetourFor(int slot) {
    switch (slot) {
        case 0:  return (void*)&Hook0;
        case 1:  return (void*)&Hook1;
        case 2:  return (void*)&Hook2;
        default: return (void*)&Hook3;
    }
}

/* 游戏可能在启动后才加载 xinput，所以每 500ms 重扫一次，把新出现的模块补上。 */
static void TryHookAll() {
    for (int slot = 0; slot < 4; slot++) {
        if (g_target[slot]) continue;
        HMODULE module = GetModuleHandleW(g_modules[slot]);
        if (!module) continue;
        void* target = (void*)GetProcAddress(module, "XInputSetState");
        if (!target) continue;
        XInputSetStateFn original = nullptr;
        if (MH_CreateHook(target, DetourFor(slot), (LPVOID*)&original) != MH_OK) continue;
        g_orig[slot] = original;
        if (MH_EnableHook(target) != MH_OK) { MH_RemoveHook(target); g_orig[slot] = nullptr; continue; }
        g_target[slot] = target;
        InterlockedIncrement(&g_hooked);
        if (g_shared) g_shared->hookedCount = (uint32_t)InterlockedCompareExchange(&g_hooked, 0, 0);
    }
}

static DWORD WINAPI WatchThread(LPVOID) {
    Sleep(80);              /* 等 DllMain 的 loader lock 释放再动内存 */
    if (MH_Initialize() != MH_OK) return 1;
    wchar_t stopName[96], startName[96];
    swprintf_s(stopName,L"Local\\WXXRumble_Stop_%lu",GetCurrentProcessId());
    swprintf_s(startName,L"Local\\WXXRumble_Start_%lu",GetCurrentProcessId());
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
    }
    return 0;
}

extern "C" __declspec(dllexport) DWORD WINAPI RumbleHookHookedCount() {
    return (DWORD)InterlockedCompareExchange(&g_hooked, 0, 0);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        CreateShared();
        HANDLE thread = CreateThread(nullptr, 0, WatchThread, nullptr, 0, nullptr);
        if (thread) CloseHandle(thread);
    }
    return TRUE;
}
