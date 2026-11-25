import random, sys, io, importlib.util, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from weighted_ground import discover_weighted, WeightedGround
from quotient import discover
from guest import Guest
from path import MASK

rng=random.Random(20261125);checks=0
for _ in range(150):
    m=rng.choice([4,8,16,32,64]);d=rng.choice([1,2,4]);base=[(rng.getrandbits(32),rng.getrandbits(32),rng.randrange(1,20)) for i in range(d)]
    rows=[]
    for p in range(m):
        a,b,w=base[p%d];delta=0 if p<d else rng.randrange(m)*(2**32//m)
        rows.append(((a+delta)&MASK,(b-delta*p)&MASK,w))
    q=discover_weighted(rows);assert len(q.rows)<=d
    for i in range(25):
        x=rng.getrandbits(32);ticks=rng.randrange(3000);cap=rng.randrange(300);y=x;n=t=0;last=None
        while n<cap:
            a,b,w=rows[y%m]
            if t+w>ticks: break
            last=y%m;y=(a*y+b)&MASK;n+=1;t+=w
        assert q.observe(x,ticks,cap)[:4]==(y,n,t,last);checks+=1
print('weighted quotient:',checks,'independent coordinate checks')
# Same state law, but distinct durations: reduction of state alone is unsound for time.
rows=[(1,1,7)]*4096
rows[-1]=(1,1,8)
assert len(discover([r[:2] for r in rows]).cases)==1
assert len(discover_weighted(rows).rows)==4096
q=discover_weighted(rows)
assert q.observe(4095,7,10)[:4]==(4095,0,0,None)
assert q.observe(4095,8,10)[:4]==(4096,1,8,4095)
print('temporal counterexample: state quotient 1; weighted quotient 4096; exact boundary verified')
# Nonidentical coefficients equal on selected residue, with alternating weights.
rows=[]
for p in range(4096):
    a=1 if p%2==0 else 5;delta=0 if p<2 else p<<20
    rows.append(((a+delta)&MASK,(1-delta*p)&MASK,7+p%2))
q=discover_weighted(rows);assert len(q.rows)==2 and q.checks==4098
# Up to 10^18 iterations within u64 time. Independent inverse of weighted time and affine formula.
queries=[(rng.getrandbits(31)*2,rng.randrange(10**19)) for _ in range(128)]
work=baseline_work=0
full=WeightedGround(4096,tuple(rows),0)
for x,t in queries:
    pairs,rem=divmod(t,15);n=pairs*2+(rem>=7);elapsed=pairs*15+7*(rem>=7)
    pow5=pow(5,pairs,2**34);v=(pow5*x+6*((pow5-1)//4))&MASK
    expected=(v+(rem>=7))&MASK
    got=q.observe(x,t,2**64-1);assert got[:3]==(expected,n,elapsed);work+=got[4]
    baseline=full.observe(x,t,2**64-1);assert baseline[:4]==got[:4];baseline_work+=baseline[4]
    if n:
        if n%2: prev=v
        else:
            prevpow=pow(5,pairs-1,2**34);prev=(prevpow*x+6*((prevpow-1)//4)+1)&MASK
        assert got[3]==prev%4096
print('4096 -> 2 weighted cases;',q.checks,'admission checks;',len(queries),'full-width time observations;',work,'charged work; full table',baseline_work)
if len(sys.argv)>1:
    source=Path(sys.argv[1])/'mailcpu/rrns.py';raw=source.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='cb1d4ba145c584c437bf38f17f2899d50f83728c'
    spec=importlib.util.spec_from_file_location('rrns',source);rrns=importlib.util.module_from_spec(spec);spec.loader.exec_module(rrns)
    for x,t in queries:
        k,rem=divmod(t,15);a,b=rrns.affine_orbit_jump(5,6,2**32,k);assert q.observe(x,t,2**64-1)[0]==(a*x+b+(rem>=7))&MASK
    print('128 time observations cross-checked by pinned E-CPU RRNS')
# Ordinary guest: identical maps and weights, but original scratch is still observed.
code=[('mov',1,0),('and',1,3),('jnz',1,5),('add',0,5),('jmp',7),('add',0,5),('jmp',7),('add',2,6),('jnz',2,0),('halt',2)]
a=Guest(code);a.r[:]=[0,0,0,4095,0,1,MASK,0]
assert a.run(7*2**32+1)==7*2**32+1 and a.halted and a.r[0]==0 and a.r[1]==4095 and a.dispatches==1
print('automatic ordinary guest:',a.lifted,'logical instructions;',a.work,'charged work; original scratch',a.r[1])
# Different weights must not reduce even when final maps agree; compare arbitrary cuts.
code=[('mov',1,0),('and',1,3),('jnz',1,5),('add',0,5),('jmp',8),('mul',0,4),('add',0,5),('jmp',8),('add',2,6),('jnz',2,0),('halt',2)]
for _ in range(30):
    a,b=Guest(code),Guest(code,mode='reference');seed=[rng.getrandbits(32),0,2000,31,1,1,MASK,0];a.r[:]=b.r[:]=seed
    while not b.halted:
        quantum=rng.randrange(1,5000);assert a.run(quantum)==b.run(quantum);assert (a.pc,a.r,a.status)==(b.pc,b.r,b.status)
print('30 unequal-duration ordinary guests, all interruption states matched')
