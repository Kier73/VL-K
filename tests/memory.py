import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'python'))
from memory import AddressSpace, Memory, PAGE, LIMIT


def rejects(kind, fn):
    try:
        fn()
    except kind:
        return
    raise AssertionError(f'expected {kind.__name__}')


rng = random.Random(912)
size = 3*PAGE+17
for pattern in (b'\0', b'abcde', bytes(range(251))):
    original = (pattern*((size+len(pattern)-1)//len(pattern)))[:size]
    a, b = Memory(size, data=original), Memory(size, pattern=pattern)
    ref = bytearray(original)
    for i in range(1000):
        start = rng.randrange(size+1)
        n = rng.randrange(min(2*PAGE,size-start)+1)
        if rng.randrange(2):
            data = rng.randbytes(n)
            a.write(start,data); b.write(start,data); ref[start:start+n]=data
        else:
            assert a.read(start,n)==b.read(start,n)==ref[start:start+n]
        if i%100==0:
            child=b.fork(); child.write(0,b'fork'); assert b.read(0,4)==ref[:4]
            assert child.read(0,4)==b'fork'
    assert a.read(0,size)==b.read(0,size)==ref
    b.write(0,original); assert b.stats()['overlay_pages']==0

s=AddressSpace(); s.map(100,10,pattern=b'ab'); s.map(110,10,pattern=b'cd',writable=False)
assert s.read(108,4)==b'abcd'
rejects(PermissionError,lambda:s.write(108,b'WXYZ')); assert s.read(108,4)==b'abcd'
s.protect(110,writable=True); s.write(108,b'WXYZ'); assert s.read(108,4)==b'WXYZ'
rejects(MemoryError,lambda:s.write(118,b'abc')); assert s.read(118,2)==b'cd'
rejects(ValueError,lambda:s.map(105,10)); rejects(ValueError,lambda:s.map(LIMIT-1,2))
s.map(1000,10,shared=True); child=s.fork(); child.write(100,b'!'); child.write(1000,b'!')
assert s.read(100,1)==b'a' and s.read(1000,1)==b'!'
child.unmap(100); assert s.read(100,1)==b'a'; rejects(MemoryError,lambda:child.read(100,1))

# A distant byte range is addressed directly; the intervening space is never materialized.
s=AddressSpace(); size=1<<40; base=1<<44; p=b'abcde'; s.map(base,size,pattern=p)
for _ in range(1000):
    i=rng.randrange(size-64); assert s.read(base+i,64)==bytes(p[(i+j)%len(p)] for j in range(64))
s.write(base+PAGE-2,b'ABCD'); s.write(base+size-1,b'!'); child=s.fork(); child.write(base+size-1,b'?')
assert s.read(base+PAGE-2,4)==b'ABCD' and s.read(base+size-1,1)==b'!' and child.read(base+size-1,1)==b'?'
stats=s.stats(base); assert stats=={'logical_bytes':size,'backing_bytes':5,'overlay_pages':3,'overlay_bytes':3*PAGE}
print('K2 memory: 3000 mixed operations, 1000 distant reads, protection, sharing, COW, cross-mapping atomic validation')
print('1 TiB logical memory:',stats)
