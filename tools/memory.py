"""Read-only process inspection used while developing NG4 extra weapon hotkeys."""
import ctypes as C
from ctypes import wintypes as W
import struct

k=C.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)];k.ReadProcessMemory.restype=W.BOOL
k.CloseHandle.argtypes=[W.HANDLE]
k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
class MODULE(C.Structure):
    _fields_=[('size',W.DWORD),('id',W.DWORD),('pid',W.DWORD),('globalUsage',W.DWORD),('processUsage',W.DWORD),('base',C.c_void_p),('bytes',W.DWORD),('module',W.HMODULE),('name',W.WCHAR*256),('path',W.WCHAR*260)]
k.Module32FirstW.argtypes=[W.HANDLE,C.POINTER(MODULE)];k.Module32FirstW.restype=W.BOOL
class Mem:
    def __init__(self,pid):
        self.h=k.OpenProcess(0x410,False,pid)
        if not self.h:raise C.WinError(C.get_last_error())
        snap=k.CreateToolhelp32Snapshot(0x18,pid)
        m=MODULE();m.size=C.sizeof(m)
        if not k.Module32FirstW(snap,C.byref(m)):raise C.WinError(C.get_last_error())
        self.base=m.base;self.size=m.bytes
        k.CloseHandle(snap)
    def read(self,addr,size):
        buf=C.create_string_buffer(size);n=C.c_size_t()
        if not k.ReadProcessMemory(self.h,addr,buf,size,C.byref(n)):raise C.WinError(C.get_last_error())
        return buf.raw[:n.value]
    def u64(self,addr):return struct.unpack('<Q',self.read(addr,8))[0]
    def u32(self,addr):return struct.unpack('<I',self.read(addr,4))[0]
    def close(self):k.CloseHandle(self.h)
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
if __name__=='__main__':
    import sys
    with Mem(int(sys.argv[1])) as m:
        print('base',hex(m.base),'size',hex(m.size))
        rva=int(sys.argv[2],16) if len(sys.argv)>2 else 0x1000
        b=m.read(m.base+rva,256)
        for i in range(0,len(b),16):print(hex(rva+i),b[i:i+16].hex(' '))
