from pathlib import Path
p=Path('overlay/tests/input.test.js');s=p.read_text(encoding='utf-8')
old=" near(wobble(.98,0),1); near(wobble(.02,0),0);                                  // 夹在 0..1"
new=" near(wobble(.98,62.5),1); near(wobble(.02,0),0);                              // 夹在 0..1"
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('assertion fixed')
