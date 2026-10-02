"""扫描 .text 里 `call qword ptr [rip+disp32]`(ff 15) 且目标等于指定导入的位置。

用法：
  python tools/api_xrefs.py CreateFileW WriteFile ReadFile MoveFileExW FlushFileBuffers ReplaceFileW
输出：调用点 RVA + 所在函数区间，便于直接跳去反汇编。
"""
from pathlib import Path
import struct, sys, re

sys.path.insert(0, str(Path(__file__).resolve().parent))
from imports import parse  # noqa: E402

GAME = Path(r'D:\APP\steam.exe\steamapps\common\NINJAGAIDEN4\NINJAGAIDEN4-steam.org')


class PE:
    def __init__(self, path=GAME):
        self.b = Path(path).read_bytes()
        b = self.b
        h = struct.unpack_from('<I', b, 0x3c)[0]
        nsec = struct.unpack_from('<H', b, h + 6)[0]
        opt = struct.unpack_from('<H', b, h + 20)[0]
        self.base = struct.unpack_from('<Q', b, h + 24 + 24)[0]
        self.sections = []
        for i in range(nsec):
            o = h + 24 + opt + i * 40
            name = b[o:o + 8].rstrip(b'\0').decode('ascii', 'replace')
            vs, va, sz, off = struct.unpack_from('<IIII', b, o + 8)
            self.sections.append((name, va, vs, off, sz))
        self.text = next(s for s in self.sections if s[0] == '.text')
        self.pdata = [struct.unpack_from('<III', b, j)
                      for j in range(next(s for s in self.sections if s[0] == '.pdata')[3],
                                     next(s for s in self.sections if s[0] == '.pdata')[3] +
                                     next(s for s in self.sections if s[0] == '.pdata')[4] - 11, 12)]
        self.starts = [f[0] for f in self.pdata]

    def function(self, rva):
        import bisect
        i = bisect.bisect_right(self.starts, rva) - 1
        if i >= 0 and self.pdata[i][0] <= rva < self.pdata[i][1]:
            return self.pdata[i][0], self.pdata[i][1]
        return rva, rva


if __name__ == '__main__':
    table = parse()
    by_rva = {}
    for va, name in table.items():
        by_rva[va - 0x140000000] = name
    pe = PE()
    name, va, vs, off, sz = pe.text
    code = pe.b[off:off + sz]
    wanted = [re.compile(p, re.I) for p in (sys.argv[1:] or ['.*'])]
    hits = {}
    for m in re.finditer(b'\xff\x15', code):
        i = m.start()
        if i + 6 > len(code):
            continue
        disp = struct.unpack_from('<i', code, i + 2)[0]
        target_rva = va + i + 6 + disp
        api = by_rva.get(target_rva)
        if not api:
            continue
        if not any(w.search(api) for w in wanted):
            continue
        call_rva = va + i
        fn = pe.function(call_rva)
        hits.setdefault(api, []).append((call_rva, fn))
    for api in sorted(hits):
        print('==', api)
        for call_rva, fn in hits[api]:
            print('   call %#x  in %#x-%#x' % (call_rva, fn[0], fn[1]))
