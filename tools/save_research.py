"""只读静态镜像分析：存档管理器（请求入口 0x102e3d0 / worker 0x102e040 / 路径 0x102d470）。

用法: python tools/save_research.py <dump|entry|worker|path|inst|code55c|vtables>
"""
import struct, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from research import PE, GAME

SAVE_ENTRY = 0x102e3d0
SAVE_WORKER = 0x102e040
SAVE_PATH = 0x102d470
DISPATCH = 0x102cee7
SIGNAL = 0x102c220

p = PE(GAME / 'NINJAGAIDEN4-steam.org')


def dis(rva, size=None):
    p.dis(rva, size)


def ptr_occurrences(value):
    """镜像里所有指向该地址的 8 字节指针（vtable / 函数指针表槽位）。
    注意必须用 VA（镜像基址+RVA），vtable 里存的是 VA，不是 RVA。"""
    out = []
    for addr in {value, p.base + value}:
        pat = struct.pack('<Q', addr)
        start = 0
        while True:
            i = p.b.find(pat, start)
            if i < 0:
                break
            out.append((p.rva(i), i, addr))
            start = i + 1
    return sorted(out)


def code_offsets(disp):
    """mov/mov r32 形式的 [reg+disp32] 访问点（mod=10 的 ModRM）。"""
    d = struct.pack('<I', disp)
    hits = []
    for name, va, vs, off, sz in p.sections:
        if name not in ('.text',):
            continue
        b = p.b[off:off + sz]
        for base_op in (0xC7, 0x89, 0x8B, 0x39, 0x3B, 0x83):
            for m in re.finditer(bytes([base_op]) + rb'[\x80-\xbf]' + re.escape(d), b, re.S):
                hits.append((va + m.start(), base_op))
    return sorted(hits)


def func_of(rva):
    a, b = p.function(rva)
    return (hex(a), hex(b))


MD = __import__('capstone').Cs(__import__('capstone').CS_ARCH_X86, __import__('capstone').CS_MODE_64)


def decode_at(rva, size=16):
    """精确解码一条指令，返回 (长度, 文本)。"""
    for ins in MD.disasm(p.data(rva, size), rva):
        return ins.size, ins.mnemonic + ' ' + ins.op_str
    return 0, '?'


def request_writes():
    """所有写 [+0x55c] 的指令：RVA、立即数、所属函数、函数调用者。"""
    out = []
    for rva, op in code_offsets(0x55c):
        n, text = decode_at(rva)
        imm = None
        if op == 0xC7 and ',' in text:
            try:
                imm = int(text.rsplit(',', 1)[1].strip(), 0)
            except ValueError:
                imm = None
        out.append((rva, op, imm, text))
    return out


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dump'
    if mode == 'entry':
        print('== 0x%x 请求入口 ==' % SAVE_ENTRY)
        print('function', func_of(SAVE_ENTRY))
        dis(SAVE_ENTRY)
    elif mode == 'worker':
        print('== 0x%x worker ==' % SAVE_WORKER)
        print('function', func_of(SAVE_WORKER))
        dis(SAVE_WORKER)
    elif mode == 'path':
        print('== 0x%x 路径拼接 ==' % SAVE_PATH)
        print('function', func_of(SAVE_PATH))
        dis(SAVE_PATH)
    elif mode == 'inst':
        print('== 0x%x signal/实例捕获点 ==' % SIGNAL)
        print('function', func_of(SIGNAL))
        dis(SIGNAL)
    elif mode == 'vtables':
        print('image base %#x' % p.base)
        for label, addr in (('entry7', SAVE_ENTRY), ('entry8', 0x102e430), ('entry6', 0x102e510),
                            ('worker', SAVE_WORKER), ('path', SAVE_PATH),
                            ('dispatch_loop', DISPATCH), ('wait', SIGNAL)):
            print('-- %#x (%s) 作为指针出现在:' % (addr, label))
            hits = ptr_occurrences(addr)
            if not hits:
                print('   (无)')
            for rva, _, addr_used in hits:
                names = [n for n, va, vs, off, sz in p.sections if off <= _ < off + sz]
                print('   rva %#x section %s xrefs %s' % (rva, names, [hex(x) for x in p.xrefs(rva)]))
    elif mode == 'code55c':
        for disp in (0x55c, 0x55a, 0x580, 0xad0):
            print('== 访问 +0x%x ==' % disp)
            for rva, op in code_offsets(disp):
                print('   %#x op %#x func %s' % (rva, op, func_of(rva)))
    elif mode == 'requests':
        print('== 写 [+0x55c] 的指令 ==')
        for rva, op, imm, text in request_writes():
            a, b = p.function(rva)
            print('  %#x  imm=%-6s  %-42s  func %#x-%#x' % (rva, imm, text, a, b))
        print()
        print('== 这些请求函数的调用者 ==')
        seen = set()
        for rva, op, imm, text in request_writes():
            a, b = p.function(rva)
            if a in seen:
                continue
            seen.add(a)
            callers = list(p.calls(a))
            print('  func %#x (imm=%s): %s' % (a, imm, [hex(x) for x in callers] or 'no direct callers'))
    elif mode == 'callers':
        addr = int(sys.argv[2], 16)
        print('== callers of %#x ==' % addr)
        for x in p.calls(addr):
            a, b = p.function(x)
            print('   %#x in func %#x-%#x' % (x, a, b))
    elif mode == 'dump':
        rva = int(sys.argv[2], 16)
        size = int(sys.argv[3], 16) if len(sys.argv) > 3 else None
        print('== %#x ==' % rva)
        dis(rva, size)
    elif mode == 'calls':
        target = int(sys.argv[2], 16)
        print('== call 0x%x ==' % target)
        for x in p.calls(target):
            print('   %#x func %s' % (x, func_of(x)))
    else:
        for addr in (SAVE_ENTRY, SAVE_WORKER, SAVE_PATH, DISPATCH, SIGNAL):
            print('== 0x%x func %s' % (addr, func_of(addr)))
            dis(addr)
            print()
