/* 震动捕获（方案A）
   - 注入 RumbleHook.dll 到目标游戏进程，DLL 内部 hook XInputSetState；
   - 从命名共享内存读回游戏写入的左右马达强度。
   本模块只做「读游戏输出 + 原样转发」，不改写游戏内存数据、不联网。
   共享内存布局必须与 native/rumble-hook/shared.h 一致（56 字节）。 */

const SHARED_NAME = 'Local\\NinjaGaidenRumble';
const SHARED_MAGIC = 0x4C424D52;   /* 'RMBL' */
const SHARED_SIZE = 56;
const FILE_MAP_READ = 0x0004;
const MEM_COMMIT = 0x1000, MEM_RESERVE = 0x2000, MEM_RELEASE = 0x8000;
const PAGE_READWRITE = 0x04;
const PROCESS_ACCESS = 0x0002 | 0x0008 | 0x0010 | 0x0020 | 0x0400;   /* CREATE_THREAD|VM_OPERATION|VM_READ|VM_WRITE|QUERY_INFORMATION */
const PROCESS_QUERY_LIMITED = 0x1000;

let api = null, loadError = '';
try {
  const koffi = require('koffi');
  const kernel32 = koffi.load('kernel32.dll');
  const psapi = koffi.load('psapi.dll');
  api = {
    koffi, kernel32, psapi,
    OpenEventW: kernel32.func('uintptr_t __stdcall OpenEventW(uint32_t access, bool inherit, const char16_t *name)'),
    SetEvent: kernel32.func('bool __stdcall SetEvent(uintptr_t handle)'),
    OpenFileMappingW: kernel32.func('uintptr_t __stdcall OpenFileMappingW(uint32_t access, bool inherit, const char16_t *name)'),
    MapViewOfFile: kernel32.func('uintptr_t __stdcall MapViewOfFile(uintptr_t mapping, uint32_t access, uint32_t high, uint32_t low, size_t bytes)'),
    UnmapViewOfFile: kernel32.func('bool __stdcall UnmapViewOfFile(uintptr_t base)'),
    CloseHandle: kernel32.func('bool __stdcall CloseHandle(uintptr_t handle)'),
    GetLastError: kernel32.func('uint32_t __stdcall GetLastError()'),
    GetTickCount64: kernel32.func('uint64_t __stdcall GetTickCount64()'),
    OpenProcess: kernel32.func('uintptr_t __stdcall OpenProcess(uint32_t access, bool inherit, uint32_t pid)'),
    VirtualAllocEx: kernel32.func('uintptr_t __stdcall VirtualAllocEx(uintptr_t process, uintptr_t addr, size_t size, uint32_t type, uint32_t protect)'),
    VirtualFreeEx: kernel32.func('bool __stdcall VirtualFreeEx(uintptr_t process, uintptr_t addr, size_t size, uint32_t type)'),
    WriteProcessMemory: kernel32.func('bool __stdcall WriteProcessMemory(uintptr_t process, uintptr_t addr, const void *buffer, size_t size, _Out_ size_t *written)'),
    CreateRemoteThread: kernel32.func('uintptr_t __stdcall CreateRemoteThread(uintptr_t process, uintptr_t attrs, size_t stack, uintptr_t start, uintptr_t param, uint32_t flags, _Out_ uint32_t *threadId)'),
    WaitForSingleObject: kernel32.func('uint32_t __stdcall WaitForSingleObject(uintptr_t handle, uint32_t ms)'),
    GetExitCodeThread: kernel32.func('bool __stdcall GetExitCodeThread(uintptr_t thread, _Out_ uint32_t *code)'),
    GetModuleHandleW: kernel32.func('uintptr_t __stdcall GetModuleHandleW(const char16_t *name)'),
    GetProcAddress: kernel32.func('uintptr_t __stdcall GetProcAddress(uintptr_t module, const char *name)'),
    EnumProcesses: psapi.func('bool __stdcall EnumProcesses(_Out_ uint32_t *pids, uint32_t size, _Out_ uint32_t *needed)'),
    QueryFullProcessImageNameW: kernel32.func('bool __stdcall QueryFullProcessImageNameW(uintptr_t process, uint32_t flags, _Out_ char16_t *name, _Inout_ uint32_t *size)')
  };
} catch (error) {
  loadError = error.message;
}

let mapping = 0, view = 0, nextRetry = 0, targetPid = 0;
function selectTarget(pid) { closeView(); targetPid = pid; nextRetry = 0; setEnabled(pid, true); }
function setEnabled(pid, enabled) {
  if (!api || !pid) return false;
  const event = api.OpenEventW(2, false, `Local\\WXXRumble_${enabled ? "Start" : "Stop"}_${pid}`);
  if (!event) return false;
  try { return api.SetEvent(event); } finally { api.CloseHandle(event); }
}

/* 没有注入时共享内存不存在，这里必须限流重试：否则 16ms 一帧都会打一次系统调用。 */
function ensureView() {
  if (view) return view;
  if (!api) return 0;
  const now = Date.now();
  if (now < nextRetry) return 0;
  nextRetry = now + 2000;
  mapping = api.OpenFileMappingW(FILE_MAP_READ, false, targetPid ? `${SHARED_NAME}_${targetPid}` : SHARED_NAME);
  if (!mapping) return 0;
  view = api.MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, SHARED_SIZE);
  if (!view) { api.CloseHandle(mapping); mapping = 0; return 0; }
  return view;
}

function closeView() {
  if (view) { api.UnmapViewOfFile(view); view = 0; }
  if (mapping) { api.CloseHandle(mapping); mapping = 0; }
}

/* 没有注入 / 没有游戏在写震动时返回 { ok:false }，调用方据此把强度归零。 */
function readRumble() {
  if (!api) return { ok: false, reason: 'koffi 不可用：' + loadError };
  const ptr = ensureView();
  if (!ptr) return { ok: false, reason: '共享内存未建立（尚未注入目标进程）' };
  try {
    const raw = Buffer.from(api.koffi.decode(ptr, api.koffi.array('uint8_t', SHARED_SIZE)));
    if (raw.readUInt32LE(0) !== SHARED_MAGIC) return { ok: false, reason: '共享内存 magic 不匹配' };
    const tickMs = Number(raw.readBigUInt64LE(32));
    const strength = raw.readFloatLE(24);
    return {
      ok: true,
      pid: raw.readUInt32LE(12),
      left: raw.readFloatLE(16),
      right: raw.readFloatLE(20),
      strength: Number.isFinite(strength) ? Math.min(1, Math.max(0, strength)) : 0,
      userIndex: raw.readUInt32LE(28),
      tickMs,
      ageMs: Math.max(0, Number(api.GetTickCount64()) - tickMs),
      writeCount: Number(raw.readBigUInt64LE(40)),
      hookedCount: raw.readUInt32LE(48),
      seq: raw.readUInt32LE(8)
    };
  } catch (error) {
    return { ok: false, reason: '读取共享内存失败：' + error.message };
  }
}

function listProcesses() {
  if (!api) return [];
  const buffer = Buffer.alloc(4 * 8192);
  const needed = [0];
  if (!api.EnumProcesses(buffer, buffer.length, needed)) return [];
  const count = Math.floor(needed[0] / 4);
  const result = [];
  const nameBuffer = Buffer.alloc(2 * 512);
  for (let i = 0; i < count; i++) {
    const pid = buffer.readUInt32LE(i * 4);
    if (!pid || pid === process.pid) continue;
    const handle = api.OpenProcess(PROCESS_QUERY_LIMITED, false, pid);
    if (!handle) continue;
    try {
      const size = [512];
      if (api.QueryFullProcessImageNameW(handle, 0, nameBuffer, size)) {
        const full = nameBuffer.toString('utf16le', 0, size[0] * 2);
        result.push({ pid, path: full, name: full.split('\\').pop() });
      }
    } finally { api.CloseHandle(handle); }
  }
  return result;
}

/* 经典 LoadLibraryW 远程线程注入。kernel32 基址在同一会话的同位数进程间一致，
   所以本进程解析出的 LoadLibraryW 地址在目标进程里同样有效。 */
function injectDll(pid, dllPath, timeoutMs = 8000) {
  if (!api) return { ok: false, error: 'koffi 不可用：' + loadError };
  if (setEnabled(pid, true)) return { ok:true, pid };
  if (!Number.isInteger(pid) || pid <= 0) return { ok: false, error: '无效的进程 id' };
  const fs = require('node:fs');
  if (!fs.existsSync(dllPath)) return { ok: false, error: '找不到 DLL：' + dllPath };

  const processHandle = api.OpenProcess(PROCESS_ACCESS, false, pid);
  if (!processHandle) return { ok: false, error: `OpenProcess 失败 (${api.GetLastError()})，可能需要管理员权限或目标进程受保护` };
  let remote = 0, thread = 0, threadFinished = false;
  try {
    const pathBytes = Buffer.from(dllPath + '\0', 'utf16le');
    remote = api.VirtualAllocEx(processHandle, 0, pathBytes.length, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remote) return { ok: false, error: 'VirtualAllocEx 失败 (' + api.GetLastError() + ')' };
    const written = [0];
    if (!api.WriteProcessMemory(processHandle, remote, pathBytes, pathBytes.length, written) || written[0] !== pathBytes.length) {
      return { ok: false, error: 'WriteProcessMemory 失败 (' + api.GetLastError() + ')' };
    }
    const loadLibrary = api.GetProcAddress(api.GetModuleHandleW('kernel32.dll'), 'LoadLibraryW');
    if (!loadLibrary) return { ok: false, error: '解析 LoadLibraryW 失败' };
    thread = api.CreateRemoteThread(processHandle, 0, 0, loadLibrary, remote, 0, [0]);
    if (!thread) return { ok: false, error: 'CreateRemoteThread 失败 (' + api.GetLastError() + ')，可能被反作弊或系统策略拦截' };
    const wait = api.WaitForSingleObject(thread, timeoutMs);
    if (wait !== 0) return { ok: false, error: '等待远程线程超时' };
    threadFinished = true;
    const exitCode = [0];
    api.GetExitCodeThread(thread, exitCode);
    if (!exitCode[0]) return { ok: false, error: '目标进程加载 DLL 失败（LoadLibraryW 返回 0），位数不匹配或路径不可访问' };
    return { ok: true, pid, moduleHandle: exitCode[0] >>> 0 };
  } finally {
    if (thread) api.CloseHandle(thread);
    if (remote && (!thread || threadFinished)) api.VirtualFreeEx(processHandle, remote, 0, MEM_RELEASE);
    api.CloseHandle(processHandle);
  }
}

function isSupported() { return !!api; }
function status() { return { supported: !!api, error: loadError, mapped: !!view }; }

module.exports = { selectTarget, setEnabled, readRumble, injectDll, listProcesses, isSupported, status, closeView, SHARED_NAME };
