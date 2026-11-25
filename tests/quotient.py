import random, sys, time, hashlib, importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from quotient import discover
from path import path_run,MASK
rng=random.Random(413)
for _ in range(100):
    m=rng.choice([4,8,16,32,64]);d=rng.choice([1,2,4]);d=min(d,m)
    base=[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(d)]
    table=[]
    for p in range(m):
        a,b=base[p%d];delta=(0 if p<d else rng.randrange(m)*(2**32//m));table.append(((a+delta)&MASK,(b-delta*p)&MASK))
    q=discover(table);assert len(q.cases)<=d
    for i in range(20):
        x=rng.getrandbits(32);n=rng.randrange(200);ref=x
        for _ in range(n):a,b=table[ref%m];ref=(a*ref+b)&MASK
        assert q.observe(x,n)[:2]==(ref,ref%m)
# A 4096-row syntactically diverse table, with two observationally distinct maps.
m=4096;table=[]
for p in range(m):
    a=1 if p%2==0 else 5;delta=0 if p<2 else (p<<20)
    table.append(((a+delta)&MASK,(1-delta*p)&MASK))
t=time.perf_counter();q=discover(table);construction=time.perf_counter()-t;assert len(q.cases)==2
bad=table[:];a,b=bad[-1];bad[-1]=(a,(b+1)&MASK);assert len(discover(bad).cases)==m
queries=[(rng.getrandbits(31)*2,rng.getrandbits(64)) for _ in range(64)]
full=[(a,b,0) for a,b in table]
t=time.perf_counter();baseline=[path_run(x,x%m,full,n,selector='residue',mode='ground') for x,n in queries];bt=time.perf_counter()-t
t=time.perf_counter();reduced=[q.observe(x,n) for x,n in queries];qt=time.perf_counter()-t
assert [r[:2] for r in baseline]==[r[:2] for r in reduced]
# Independently compute alternating affine pair x -> 5*x+6 using a modular 2x2 law via a lifted modulus.
for (x,n),r in zip(queries,reduced):
    k=n//2;v=(pow(5,k,2**34)*x+6*((pow(5,k,2**34)-1)//4))&MASK
    assert r[:2]==((v+n%2)&MASK,((v+n%2)&MASK)%m)
print('2000 iterative checks; adversarial single-row exception prevents collapse')
print('4096 ->',len(q.cases),'selector cases;',q.checks,'construction checks; 64 queries; charged navigation work',sum(r[2] for r in baseline),'->',sum(r[2] for r in reduced))
print('seconds full',round(bt,6),'reduced',round(qt,6),'construction',round(construction,6))
if len(sys.argv)>1:
    source=Path(sys.argv[1])/'mailcpu/rrns.py';raw=source.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='cb1d4ba145c584c437bf38f17f2899d50f83728c'
    spec=importlib.util.spec_from_file_location('rrns',source);rrns=importlib.util.module_from_spec(spec);spec.loader.exec_module(rrns)
    for (x,n),r in zip(queries,reduced):
        a,b=rrns.affine_orbit_jump(5,6,2**32,n//2);assert r[0]==(a*x+b+n%2)&MASK
    print('64 full-width observations independently cross-checked by pinned E-CPU RRNS')
# Use the research service as an actual CLI application, with binary-safe pipes.
import json, tempfile
from process import Supervisor, PIPE
with tempfile.TemporaryDirectory() as d, Supervisor() as sup:
    file=Path(d)/'table.json';file.write_text(json.dumps(table))
    h=sup.spawn([str(ROOT/'dist/vlk'),'ground',str(file)],stdin=PIPE,stdout=PIPE,stderr=PIPE)
    payload=''.join(json.dumps({'x':x,'count':str(n)})+'\n' for x,n in queries).encode()
    out,err=sup.communicate(h,payload,timeout=20);assert sup.wait(h)==0 and not err
    responses=[json.loads(line) for line in out.splitlines()]
    assert responses[0]=={'original_cases':4096,'reduced_cases':2,'checks':4098}
    assert [(r['x'],r['phase']) for r in responses[1:]]==[r[:2] for r in reduced]
print('actual vlk ground service: 64 requests, exact output')
