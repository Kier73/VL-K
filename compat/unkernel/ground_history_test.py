from pathlib import Path
from tempfile import TemporaryDirectory
import random
import sqlite3
import subprocess
import sys
from ground_history import GroundHistory, Conflict, ZERO, PAGE_SIZE

if len(sys.argv)>1:
    h=GroundHistory(sys.argv[1]);rev=int(sys.argv[2])
    try:
        h.commit('main',rev,{7:bytes([int(sys.argv[3])])*PAGE_SIZE})
    except Conflict:
        sys.exit(3)
    finally:
        h.close()
    sys.exit(0)

with TemporaryDirectory() as tmp:
    path=Path(tmp)/'ground.sqlite';rng=random.Random(419)
    basis=rng.randbytes(PAGE_SIZE);h=GroundHistory(path,pages=16384,bases=[basis]);start=h.head()
    # The E-CPU codec is exercised with an incompressible raw basis and sparse XOR.
    changes={};states={start:{}};r=start
    for t in range(64):
        i=(t*257)%h.pages;b=bytearray(basis);b[123]^=t+1;raw=bytes(b)
        before=h.db.execute('SELECT count(*) FROM node').fetchone()[0]
        new=h.commit('main',r,{i:raw});after=h.db.execute('SELECT count(*) FROM node').fetchone()[0]
        assert after-before<=h.depth and new!=r
        changes[i]=raw;states[new]=changes.copy();r=new
    counts=h.backing.counts();assert counts[2][0]==64 and counts[0][0]==1
    print('64 revisions: 64 XOR delta pages, one raw basis, <=14 new coordinate nodes per update')
    h.fork('alternative',start);a=h.commit('alternative',start,{0:basis});assert h.head()==r and h.observe(a,0)==basis and h.observe(start,0)==ZERO
    assert h.commit('main',r,{0:changes[0]})==r
    for _ in range(1000):
        rev=rng.choice(list(states));i=rng.choice(list(states[rev]) or [0]) if rng.randrange(2) else rng.randrange(h.pages)
        assert h.observe(rev,i)==states[rev].get(i,ZERO)
    print('1000 historical observations, independent branch, no-op and zero semantics passed')
    h.fork('range',start)
    payload=rng.randbytes(1536);v=h.write_range('range',start,PAGE_SIZE-512,payload)
    assert h.read_range(v,0,3*PAGE_SIZE)==bytes(PAGE_SIZE-512)+payload+bytes(2*PAGE_SIZE-1024)
    assert h.read_range(start,PAGE_SIZE-512,1536)==bytes(1536)
    h.fork('reverse',start)
    v2=h.commit('reverse',start,{1:h.observe(v,1),0:h.observe(v,0)})
    assert h.root(v)==h.root(v2)
    assert h.root(h.write_range('range',v,PAGE_SIZE-512,bytes(1536)))==h.root(start)
    try:h.write_range('reverse',v2,h.pages*PAGE_SIZE-512,bytes(1024));raise AssertionError('range accepted')
    except ValueError:pass
    assert h.head('reverse')==v2
    print('cross-page sector writes, root equivalence, zero reclamation and range refusal passed')
    h.close()
    children=[subprocess.Popen([sys.executable,__file__,str(path),str(r),str(x)]) for x in (77,88)]
    assert sorted(p.wait() for p in children)==[0,3]
    h=GroundHistory(path);winner=h.head();assert h.observe(winner,7) in (bytes([77])*PAGE_SIZE,bytes([88])*PAGE_SIZE)
    assert h.observe(r,7)==ZERO and h.observe(a,0)==basis
    try:h.commit('main',r,{1:basis});raise AssertionError('stale accepted')
    except Conflict:pass
    # Corrupt a retained root; navigation to an independent branch still works.
    key=h.root(winner);h.db.execute('UPDATE node SET l=? WHERE hash=?',('f'*64,key));h.db.commit()
    try:h.observe(winner,7);raise AssertionError('tampered path accepted')
    except ValueError:pass
    assert h.observe(a,0)==basis
    h.close()
    print('fresh-process CAS race, historical reopen and tampered coordinate path rejection passed')
