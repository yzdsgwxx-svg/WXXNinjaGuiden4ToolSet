"""在运行中的游戏进程里定位 SaveDataManager 实例。

依据：实例 +0xa88 处是 std::wstring（存档目录路径），+0x55c 是请求码(0..10)，
+0xad8 是退出标志(byte)。先按 UTF-16 路径字符串命中，再回推 -0xa88 校验。
只读，不改游戏内存。

用法：python tools/find_savedata.py <pid> [关键字，默认 NINJAGAIDEN4]
"""
import ctypes as C
from ctypes import wintypes as W
import struct, sys

k = C.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.OpenProcess.restype = W.HANDLE
k.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
k.ReadProcessMemory.restype = W.BOOL
k.VirtualQueryEx.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t]
k.VirtualQueryEx.restype = C.c_size_t
k.CloseHandle.argtypes = [W.HANDLE]


class MBI(C.Structure):
    _fields_ = [('BaseAddress', C.c_void_p), ('AllocationBase', C.c_void_p), ('AllocationProtect', W.DWORD),
                ('RegionSize', C.c_size_t), ('State', W.DWORD), ('Protect', W.DWORD), ('Type', W.DWORD)]


MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01


def readable(prot):
    return prot != 0 and not (prot & PAGE_GUARD) and not (prot & PAGE_NOACCESS)


def main():
    pid = int(sys.argv[1])
    needle = (sys.argv[2] if len(sys.argv) > 2 else 'NINJAGAIDEN4').encode('utf-16-le')
    h = k.OpenProcess(0x0410, False, pid)
    if not h:
        raise SystemExit('OpenProcess failed %d' % C.get_last_error())
    addr = 0
    mbi = MBI()
    scanned = 0
    hits = []
    CHUNK = 1 << 20
    while k.VirtualQueryEx(h, C.c_void_p(addr), C.byref(mbi), C.sizeof(mbi)):
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize
        if mbi.State == MEM_COMMIT and readable(mbi.Protect) and size:
            pos = 0
            while pos < size:
                n = min(CHUNK, size - pos)
                buf = C.create_string_buffer(n)
                read = C.c_size_t()
                if k.ReadProcessMemory(h, C.c_void_p(base + pos), buf, n, C.byref(read)) and read.value:
                    data = buf.raw[:read.value]
                    scanned += len(data)
                    off = 0
                    while True:
                        i = data.find(needle, off)
                        if i < 0:
                            break
                        hits.append(base + pos + i)
                        off = i + 1
                pos += n
        nxt = base + size
        if nxt <= addr:
            break
        addr = nxt
    print('scanned %.1f MB, %d string hits' % (scanned / 1048576.0, len(hits)))
    for hit in hits:
        inst = hit - 0xa88
        raw = C.create_string_buffer(0xB00)
        read = C.c_size_t()
        if not k.ReadProcessMemory(h, C.c_void_p(inst), raw, 0xB00, C.byref(read)):
            continue
        b = raw.raw
        code = struct.unpack_from('<i', b, 0x55c)[0]
        flag = b[0xad8]
        strlen = struct.unpack_from('<Q', b, 0xa98)[0]
        cap = struct.unpack_from('<Q', b, 0xaa0)[0]
        ptr = struct.unpack_from('<Q', b, 0xa88)[0]
        if 0 <= code <= 12 and strlen < 260 and cap < 0x1000 and ptr == hit:
            print('CANDIDATE inst=%#x  +0x55c=%d  +0xad8=%d  path_len=%d cap=%d' % (inst, code, flag, strlen, cap))
        else:
            print('  (hit %#x -> inst %#x rejected: code=%d len=%d cap=%d ptr==hit:%s)' % (hit, inst, code, strlen, cap, ptr == hit))
    k.CloseHandle(h)


if __name__ == '__main__':
    main()
