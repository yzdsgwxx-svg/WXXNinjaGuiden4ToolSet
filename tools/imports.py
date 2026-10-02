"""把 IAT 地址翻成 模块!函数名，配合 research.py dis 里的 `call qword ptr [rip+X]` 使用。

用法：
  python tools/imports.py list                 # 列出全部导入（含 IAT 地址）
  python tools/imports.py name 0x20c69c8       # 查单个 IAT 地址
  python tools/imports.py find WriteFile       # 按名字搜
"""
from pathlib import Path
import struct, sys

GAME = Path(r'D:\APP\steam.exe\steamapps\common\NINJAGAIDEN4\NINJAGAIDEN4-steam.org')


def parse(path=GAME):
    b = Path(path).read_bytes()
    h = struct.unpack_from('<I', b, 0x3c)[0]
    nsec = struct.unpack_from('<H', b, h + 6)[0]
    opt = struct.unpack_from('<H', b, h + 20)[0]
    image_base = struct.unpack_from('<Q', b, h + 24 + 24)[0]
    sections = []
    for i in range(nsec):
        o = h + 24 + opt + i * 40
        vs, va, sz, off = struct.unpack_from('<IIII', b, o + 8)
        sections.append((va, vs, off, sz))
    def rva2off(rva):
        for va, vs, off, sz in sections:
            if va <= rva < va + max(vs, sz):
                return off + rva - va
        return None
    def read(rva, size):
        o = rva2off(rva)
        return b[o:o + size] if o is not None else None
    # DataDirectory[1] = import table
    dd = h + 24 + (opt - 0) + (96 if opt >= 112 else 96)
    imp_rva, imp_size = struct.unpack_from('<II', b, h + 24 + 96 + 8 + 0)  # 占位，下面重算
    # PE32+ optional header: NumberOfRvaAndSizes 在 +108，DataDirectory 从 +112 开始
    dd_off = h + 24 + 112
    imp_rva, imp_size = struct.unpack_from('<II', b, dd_off + 8)
    out = {}
    i = 0
    while True:
        d = read(imp_rva + i * 20, 20)
        if not d:
            break
        oft, tstamp, fwd, name_rva, first_thunk = struct.unpack('<IIIII', d)
        if not name_rva and not first_thunk:
            break
        dll = (read(name_rva, 64) or b'').split(b'\0')[0].decode('ascii', 'replace')
        int_rva = oft or first_thunk
        j = 0
        while True:
            ent = read(int_rva + j * 8, 8)
            if not ent:
                break
            v = struct.unpack('<Q', ent)[0]
            if v == 0:
                break
            iat_rva = first_thunk + j * 8
            if v & (1 << 63):
                fname = 'ordinal#%d' % (v & 0xffff)
            else:
                nb = read(v + 2, 128) or b''
                fname = nb.split(b'\0')[0].decode('ascii', 'replace')
            out[image_base + iat_rva] = '%s!%s' % (dll, fname)
            j += 1
        i += 1
    return out


if __name__ == '__main__':
    table = parse()
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if mode == 'name':
        target = int(sys.argv[2], 16)
        hit = table.get(target)
        if hit is None:
            near = sorted((abs(a - target), a) for a in table)[:3]
            print('not found; nearest:', [(hex(a), table[a]) for _, a in near])
        else:
            print(hex(target), hit)
    elif mode == 'find':
        import re
        pat = re.compile(sys.argv[2], re.I)
        for a, name in sorted(table.items()):
            if pat.search(name):
                print(hex(a), name)
    else:
        for a, name in sorted(table.items()):
            print(hex(a), name)
