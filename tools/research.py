"""Local, read-only PE analysis helpers. Addresses printed as RVAs."""
from pathlib import Path
import struct, re, sys, bisect
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

GAME=Path(r'D:\APP\steam.exe\steamapps\common\NINJAGAIDEN4')
class PE:
    def __init__(self,path):
        self.b=Path(path).read_bytes()
        h=struct.unpack_from('<I',self.b,0x3c)[0]
        n=struct.unpack_from('<H',self.b,h+6)[0]
        opt=struct.unpack_from('<H',self.b,h+20)[0]
        self.base=struct.unpack_from('<Q',self.b,h+24+24)[0]
        self.sections=[]
        for i in range(n):
            o=h+24+opt+i*40
            vs,va,sz,off=struct.unpack_from('<IIII',self.b,o+8)
            self.sections.append((self.b[o:o+8].rstrip(b'\0').decode(),va,vs,off,sz))
        self.funcs=[]
        for name,va,vs,off,sz in self.sections:
            if name=='.pdata':
                self.funcs=[struct.unpack_from('<III',self.b,j) for j in range(off,off+sz-11,12)]
        self.starts=[f[0] for f in self.funcs]
        self.cs=Cs(CS_ARCH_X86,CS_MODE_64)
    def off(self,rva):
        for _,va,vs,off,sz in self.sections:
            if va<=rva<va+sz:return off+rva-va
        raise ValueError(hex(rva))
    def rva(self,offset):
        for _,va,vs,off,sz in self.sections:
            if off<=offset<off+sz:return va+offset-off
        raise ValueError(hex(offset))
    def data(self,rva,size):
        o=self.off(rva);return self.b[o:o+size]
    def function(self,rva):
        i=bisect.bisect_right(self.starts,rva)-1
        if i>=0 and self.funcs[i][0]<=rva<self.funcs[i][1]:return self.funcs[i][:2]
        return rva,rva+160
    def dis(self,rva,size=None):
        if size is None:
            rva,end=self.function(rva);size=end-rva
        for a,s,m,o in self.cs.disasm_lite(self.data(rva,size),rva):print(f'{a:08x} {m:8} {o}')
    def xrefs(self,target):
        for name,va,vs,off,sz in self.sections:
            if name!='.text':continue
            b=self.b[off:off+sz]
            # RIP-relative memory operands, then decode to confirm target.
            for m in re.finditer(rb'[\x48-\x4f]?[\x8b\x8d\x89\x3b\x39\xff][\x05\x0d\x15\x1d\x25\x2d\x35\x3d].{4}',b,re.S):
                end=m.end();disp=struct.unpack_from('<i',b,end-4)[0]
                if va+end+disp==target:
                    yield va+m.start()
    def calls(self,target):
        for name,va,vs,off,sz in self.sections:
            if name!='.text':continue
            b=self.b[off:off+sz]
            for m in re.finditer(b'\xe8',b):
                i=m.start()
                if i+5<=len(b) and va+i+5+struct.unpack_from('<i',b,i+1)[0]==target:yield va+i

if __name__=='__main__':
    p=PE(GAME/'NINJAGAIDEN4-steam.org')
    mode=sys.argv[1]
    if mode=='strings':
        for m in re.finditer(rb'[\x20-\x7e]{5,}',p.b):
            if re.search(sys.argv[2],m.group().decode(),re.I):
                r=p.rva(m.start());print(hex(r),m.group().decode(), 'XREFS',[(hex(x),tuple(hex(y) for y in p.function(x))) for x in p.xrefs(r)])
    elif mode=='dis':p.dis(int(sys.argv[2],16),int(sys.argv[3],16) if len(sys.argv)>3 else None)
    elif mode=='calls':
        for x in p.calls(int(sys.argv[2],16)):print(hex(x),tuple(hex(y) for y in p.function(x)))
