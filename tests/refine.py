"""Independent iteration, weighted cycle oracle, counterexamples, and actual CLI."""
import bisect, hashlib, importlib.util, io, json, random, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from refine import refine, SparseClock
from weighted_ground import discover_weighted
from guest import Guest
from path import MASK
from process import Supervisor, PIPE

rng=random.Random(891);checks=0
for _ in range(400):
    m=rng.choice([8,16,32,64,128]);stride=rng.choice([0,1,2,4,8,rng.getrandbits(32)]);base=rng.randrange(2,20)
    exceptions={p:rng.choice([1,base+1,base+5]) for p in rng.sample(range(m),rng.randrange(m//8+1))}
    # Deliberately disguise every row, including row zero and row one.
    rows=[]
    for p in range(m):
        delta=rng.randrange(m)*(2**32//m)
        rows.append(((1+delta)&MASK,(stride-delta*p)&MASK,exceptions.get(p,base)))
    result=refine(rows);g=result.ground;assert isinstance(g,SparseClock) and g.stride==stride and result.checks==m
    for _ in range(25):
        x=rng.getrandbits(32);t=rng.randrange(5000);cap=rng.randrange(400);y=x;n=elapsed=0;last=None
        while n<cap:
            a,b,w=rows[y%m]
            if elapsed+w>t:break
            last=y%m;y=(a*y+b)&MASK;n+=1;elapsed+=w
        assert g.observe(x,t,cap)[:4]==(y,n,elapsed,last);checks+=1
print('sparse clock:',checks,'independent sequential coordinate checks')

# Refusal exposes an actual differing state, and exact dense fallback remains available.
rows=[(1,1,7)]*4096;rows[-1]=(1,1,8)
ref=refine(rows);g=ref.ground;assert isinstance(g,SparseClock) and g.exceptions==((4095,8),)
assert len(discover_weighted(rows).rows)==4096
bad=rows[:];bad[-1]=(1,2,8);r=refine(bad);assert r.reason=='state law differs'
x,a,b=r.witness;A,B,_=bad[x%4096];assert a==(A*x+B)&MASK and b==(x+1)&MASK and a!=b
assert not isinstance(r.ground,SparseClock)
assert refine([(3,1,7)]*16).reason=='nontranslation state law'
assert refine([(1,1,7+p%2) for p in range(16)]).reason=='dense exceptions'
try:g.observe(0,100,100,budget=0);raise AssertionError('budget bypass')
except RuntimeError:pass
# Direct independent cycle prefix and rank via bisect, at arbitrary u64 coordinates.
# Build each cycle by sequentially visiting residues, not by congruence inversion.
def oracle(rows,x,t,cap,stride):
    m=len(rows);p=x%m;prefix=[0];start=p
    while True:
        prefix.append(prefix[-1]+rows[p][2]);p=(p+stride)%m
        if p==start:break
    period=len(prefix)-1;k,r=divmod(t,prefix[-1]);n=min(cap,k*period+bisect.bisect_right(prefix,r)-1)
    k,r=divmod(n,period);elapsed=k*prefix[-1]+prefix[r]
    return (x+stride*n)&MASK,n,elapsed,(x+stride*(n-1))%m if n else None
for stride in (0,1,2,4,4096,0xffffffff,0x80000002):
    rr=[(1,stride,7)]*4096;rr[0]=(1,stride,2);rr[4095]=(1,stride,8)
    clock=refine(rr).ground
    for _ in range(40):
        x=rng.getrandbits(32);t=rng.getrandbits(64);cap=rng.getrandbits(64)
        assert clock.observe(x,t,cap)[:4]==oracle(rr,x,t,cap,stride)
print('280 full-width cases with shorter/longer, reachable/unreachable exceptions')
queries=[(rng.getrandbits(32),rng.getrandbits(64),rng.getrandbits(64)) for _ in range(128)]
full=discover_weighted(rows)
t=time.perf_counter();baseline=[full.observe(*q) for q in queries];bt=time.perf_counter()-t
t=time.perf_counter();small=[g.observe(*q) for q in queries];st=time.perf_counter()-t
assert [r[:4] for r in baseline]==[r[:4] for r in small]
assert [r[:4] for r in small]==[oracle(rows,*q,1) for q in queries]
print('4096 -> translation + default + 1 exception;',ref.checks,'admission checks; charged units',sum(r[4] for r in baseline),'->',sum(r[4] for r in small),'seconds',round(bt,6),'->',round(st,6))
# Cross-check state realization using E-CPU's actual source-pinned utility if supplied.
if len(sys.argv)>1:
    source=Path(sys.argv[1])/'mailcpu/rrns.py';raw=source.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='cb1d4ba145c584c437bf38f17f2899d50f83728c'
    spec=importlib.util.spec_from_file_location('rrns',source);rrns=importlib.util.module_from_spec(spec);spec.loader.exec_module(rrns)
    for (x,t,cap),(y,n,elapsed,last,w) in zip(queries,small):
        A,B=rrns.affine_orbit_jump(1,1,2**32,n);assert y==(A*x+B)&MASK
    print('128 full-width state observations cross-checked with pinned E-CPU RRNS')
# Actual ordinary guest: zero-residue arm is eight instructions, others seven.
code=[('mov',1,0),('and',1,3),('jnz',1,6),('mul',0,4),('add',0,5),('jmp',8),('add',0,5),('jmp',8),('add',2,6),('jnz',2,0),('halt',2)]
seed=[0,0,0,4095,1,1,MASK,0];a=Guest(code);a.r[:]=seed
end=7*2**32+2**20+1
# Inside the last branch, then exact completion. Last residue is 4095.
assert a.run(end-3)==end-3 and a.pc==8 and a.r[0]==0 and a.r[1]==4095 and a.r[2]==1
assert a.run(3)==3 and a.halted and a.r[2]==0
print('ordinary guest:',a.lifted,'lifted instructions;',a.dispatches,'ordinary dispatches;',a.work,'charged work')
for _ in range(100):
    seed=[rng.getrandbits(32),0,rng.randrange(1,1200),rng.choice([7,15,63,4095]),1,rng.choice([0,1,2,8]),MASK,0]
    a,b=Guest(code),Guest(code,mode='reference');a.r[:]=b.r[:]=seed
    while not b.halted:
        q=rng.randrange(1,3000);assert a.run(q)==b.run(q);assert (a.pc,a.r,a.status,a.halted)==(b.pc,b.r,b.status,b.halted)
print('100 ordinary guests, random interruption and continuation')
with tempfile.TemporaryDirectory() as d,Supervisor() as sup:
    file=Path(d)/'table.json';file.write_text(json.dumps(rows));h=sup.spawn([str(ROOT/'dist/vlk'),'refine',str(file)],stdin=PIPE,stdout=PIPE,stderr=PIPE)
    payload=''.join(json.dumps({'x':x,'ticks':str(t),'maximum':str(n)})+'\n' for x,t,n in queries).encode()
    out,err=sup.communicate(h,payload,timeout=20);assert sup.wait(h)==0 and not err
    response=[json.loads(line) for line in out.splitlines()];assert response[0]['method']=='SparseClock' and response[0]['exceptions']==1
    assert [(r['x'],int(r['iterations']),int(r['elapsed']),r['last']) for r in response[1:]]==[r[:4] for r in small]
print('actual vlk refine process: 128 verified observations')
