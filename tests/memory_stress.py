"""Independent byte-wise oracle, host mmap and real SQLite file workloads."""
import hashlib
import mmap
import random
import sqlite3
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from memory import AddressSpace, Memory, PAGE, LIMIT


def outcome(fn):
    try:
        return ('ok', fn())
    except (MemoryError, PermissionError, ValueError, KeyError, TypeError) as exc:
        return (type(exc).__name__, None)


class Oracle:
    """No interval index, no page overlays; eager bytes and linear lookup."""
    def __init__(self):
        self.maps = {}

    def map(self, a, size, data, writable, shared):
        if any(a < b+len(buf) and b < a+size for b,(buf,_,_) in self.maps.items()):
            raise ValueError
        self.maps[a] = (bytearray(data), writable, shared)

    def loc(self, a, write=False):
        for b,(buf,w,_) in self.maps.items():
            if b <= a < b+len(buf):
                if write and not w: raise PermissionError
                return buf,a-b
        raise MemoryError

    def read(self, a, n):
        return bytes(buf[i] for buf,i in (self.loc(j) for j in range(a,a+n)))

    def write(self, a, data):
        targets = [self.loc(j, True) for j in range(a,a+len(data))]
        for (buf,i),v in zip(targets,data): buf[i] = v
        return len(data)

    def fork(self):
        child = Oracle()
        child.maps = {a:(buf if shared else bytearray(buf), w, shared) for a,(buf,w,shared) in self.maps.items()}
        return child

    def protect(self,a,w):
        buf,_,s = self.maps[a]; self.maps[a] = (buf,w,s)

    def unmap(self,a): del self.maps[a]


rng = random.Random(0x564c4b)
spaces = [(AddressSpace(), Oracle())]
counts = dict()
for step in range(20000):
    a,o = rng.choice(spaces)
    op = rng.randrange(7)
    start = rng.randrange(0,256)
    n = rng.randrange(1,65)
    if op == 0:
        p = rng.randbytes(rng.randrange(1,13)); data = (p*((n+len(p)-1)//len(p)))[:n]
        w,shared = bool(rng.randrange(2)),bool(rng.randrange(2))
        x = outcome(lambda:a.map(start,n,pattern=p,writable=w,shared=shared))
        y = outcome(lambda:o.map(start,n,data,w,shared))
    elif op == 1:
        x=outcome(lambda:a.read(start,n));y=outcome(lambda:o.read(start,n))
    elif op == 2:
        data=rng.randbytes(n)
        x=outcome(lambda:a.write(start,data));y=outcome(lambda:o.write(start,data))
    elif op == 3:
        if o.maps and rng.randrange(4): start=rng.choice(list(o.maps))
        w=bool(rng.randrange(2)); x=outcome(lambda:a.protect(start,writable=w));y=outcome(lambda:o.protect(start,w))
    elif op == 4:
        if o.maps and rng.randrange(4): start=rng.choice(list(o.maps))
        x=outcome(lambda:a.unmap(start)); y=outcome(lambda:o.unmap(start))
    elif op == 5:
        if len(spaces)==8: spaces.pop(rng.randrange(1,8))
        spaces.append((a.fork(),o.fork()));x=y=('ok',None)
    else:
        for va,vo in spaces:
            for address,(buf,_,_) in vo.maps.items():
                assert va.read(address,len(buf))==buf
        x=y=('ok',None)
    assert x==y,(step,op,x,y)
    counts[x[0]]=counts.get(x[0],0)+1
    if step%100==0:
        for va,vo in spaces:
            for address,(buf,_,_) in vo.maps.items(): assert va.read(address,len(buf))==buf
print('Address-space state machine: 20000 operations;',counts)

# Confirm rejection of ambiguous address and data types, with no mutation.
a=AddressSpace();a.map(1,8,pattern=b'Z')
for fn in (lambda:a.protect(True,writable=False),lambda:a.unmap(1.0),lambda:a.stats(True)):
    assert outcome(fn)[0]=='ValueError'
for fn in (lambda:a.write(1,4),lambda:Memory(4,data=4),lambda:Memory(4,pattern=4)):
    assert outcome(fn)[0]=='TypeError'
assert a.read(1,8)==b'Z'*8
assert a.write(1,memoryview(b'XY'))==2
assert a.read(1,8)==b'XY'+b'Z'*6
# Edge addresses, including exclusive end.
a.map(LIMIT-8,8,pattern=b'xy');assert a.read(LIMIT-2,2)==b'xy'
assert outcome(lambda:a.write(LIMIT-1,b'ab'))[0]=='ValueError'
assert a.read(LIMIT-1,1)==b'y'

# Independently implemented host mmap and a non-page-aligned backing period.
size=8<<20; pattern=rng.randbytes(8191); base=(pattern*((size+len(pattern)-1)//len(pattern)))[:size]
with mmap.mmap(-1,size) as mm:
    mm[:]=base; m=Memory(size,pattern=pattern)
    for step in range(20000):
        n=rng.randrange(1,8193); a=rng.randrange(size-n+1)
        if step%3==0:
            data=rng.randbytes(n);mm[a:a+n]=data;m.write(a,data)
        else: assert m.read(a,n)==mm[a:a+n]
    assert hashlib.sha256(m.read(0,size)).digest()==hashlib.sha256(mm[:]).digest()
print('Host mmap differential: 20000 mixed operations and full 8 MiB digest')

# SQLite is an independent consumer of real database pages, not a second memory law.
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'source.db'; q=Path(d)/'reconstructed.db'; old=Path(d)/'old.db'
    with sqlite3.connect(p) as db:
        db.execute('PRAGMA journal_mode=DELETE');db.execute('CREATE TABLE items (id INTEGER PRIMARY KEY, payload BLOB, score INTEGER)')
        db.executemany('INSERT INTO items VALUES (?,?,?)',((i,rng.randbytes(100),i%97) for i in range(8000)))
        db.commit()
    original=p.read_bytes(); m=Memory(len(original),data=original); snapshot=m.fork()
    with sqlite3.connect(p) as db:
        db.execute('UPDATE items SET score=score+1000 WHERE id%7=0');db.commit()
        expected=db.execute('SELECT COUNT(*), SUM(score), MIN(score), MAX(score) FROM items').fetchone()
    updated=p.read_bytes();assert len(updated)==len(original)
    changed=0
    for i in range(0,len(updated),PAGE):
        if original[i:i+PAGE]!=updated[i:i+PAGE]: m.write(i,updated[i:i+PAGE]);changed+=1
    q.write_bytes(m.read(0,len(updated)));old.write_bytes(snapshot.read(0,len(original)))
    with sqlite3.connect(q) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
        assert db.execute('SELECT COUNT(*), SUM(score), MIN(score), MAX(score) FROM items').fetchone()==expected
    with sqlite3.connect(old) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
        assert db.execute('SELECT MAX(score) FROM items').fetchone()==(96,)
    assert m.stats()['overlay_pages']==changed
    assert q.read_bytes()==updated and old.read_bytes()==original
    print('SQLite: 8000 real rows;',len(updated),'bytes;',changed,'changed pages; both snapshots integrity_check ok; aggregate',expected)
