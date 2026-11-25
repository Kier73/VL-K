import io, random, sys, copy, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from guest import Guest
from path import MASK
from loop_receipt import issue, verify, digest


def loop(left,right):
    branch=4+len(left);tail=branch+len(right)+1
    return [('mov',1,0),('and',1,3),('jnz',1,branch),*left,('jmp',tail),*right,('jmp',tail),('add',2,6),('jnz',2,0),('write',0),('halt',2)]


def guest(code, seed, mode):
    g=Guest(code,mode=mode,output_stream=io.BytesIO());g.r[:]=seed;return g


def state(g):return g.pc,g.r[:],g.halted,g.status,g.output.getvalue()

rng=random.Random(531);checks=lifted=0
for _ in range(700):
    arms=[[(rng.choice(['mul','add']),0,rng.choice([4,5,7])) for _ in range(n)] for n in rng.sample(range(1,7),2)]
    code=loop(*arms);seed=[rng.getrandbits(32),0,rng.randrange(1,600),rng.choice([0,1,3,7,15,31]),rng.getrandbits(32),rng.getrandbits(32),MASK,rng.getrandbits(32)]
    a,b=guest(code,seed,'auto'),guest(code,seed,'reference')
    # Independent scalar oracle, including the logical length selected by each branch.
    x=seed[0];t=0
    for i in range(seed[2]):
        p=x&seed[3];arm=arms[bool(p)];t+=len(arm)+6
        for op,_,r in arm:x=(x*seed[r] if op=='mul' else x+seed[r])&MASK
    observed=0
    while not b.halted:
        q=rng.randrange(1,1500);n=a.run(q);assert n==b.run(q);observed+=n
        assert state(a)==state(b);checks+=1
    assert (a.r[0],a.r[1],observed)==(x,p,t+2)
    lifted+=a.lifted
assert lifted>0
print('700 unequal branch programs;',checks,'matching interruption states;',lifted,'lifted logical instructions')
# even x -> x+1 (7 instructions), odd -> 3*x+1 (8 instructions)
code=loop([('add',0,5)],[('mul',0,7),('add',0,5)])
seed=[0,0,0,1,1,1,MASK,3];pairs=2**31;total=15*pairs
# Test an observation inside the odd arm after the last complete even iteration.
cut=15*(pairs-1)+7+4
r=issue(code,seed,0,cut);assert verify(json.loads(json.dumps(r)),code,seed,0,cut)
assert r['body']['elapsed']==cut-4 and r['body']['iterations']==2**32-1
x=(2*(pow(3,pairs-1,2**32)-1))&MASK
assert r['body']['registers']==[x+1,0,1,1,1,1,MASK,3]
a=guest(code,seed,'auto');assert a.run(cut)==cut
# At four instructions into the odd path: mov, and, jnz, mul.
assert a.pc==6 and a.r[0]==3*(x+1)&MASK and a.r[1]==1 and a.r[2]==1
assert a.run(total+2-cut)==total+2-cut and a.halted
assert a.r[0]==(2*(pow(3,pairs,2**32)-1))&MASK and a.r[2]==0
print('large weighted trajectory:',total,'logical loop instructions;',a.lifted,'lifted;',a.dispatches,'ordinary dispatches;',a.work,'charged work')
for key in ('elapsed','iterations','end_pc','work'):
    bad=copy.deepcopy(r);bad['body'][key]+=1;bad['sha256']=digest(bad['body']);assert not verify(bad,code,seed,0,cut)
bad=copy.deepcopy(r);bad['body']['registers'][0]^=1;bad['sha256']=digest(bad['body']);assert not verify(bad,code,seed,0,cut)
assert not verify(r,code,seed,0,cut+1)
changed=code[:];changed[-1]=('halt',1);assert not verify(r,changed,seed,0,cut)
print('receipt transport and seven tamper/context rejection cases')
# Actual launcher and supervised binary pipeline, full logical coordinate.
from process import Supervisor, PIPE
root=Path(__file__).resolve().parents[1]
with Supervisor() as supervisor:
    hs=supervisor.pipeline([[str(root/'dist/vlk'),'guest',str(root/'examples/guest-weighted.json'),'--budget',str(total+9)],['od','-An','-tu1']],stdout=PIPE)
    output,_=supervisor.communicate(hs[-1],timeout=10)
    assert output.split()==[b'0'] and [supervisor.wait(h,timeout=10) for h in hs]==[0,0]
print('supervised vlk guest | od:',total+9,'logical instructions, output',output.strip().decode())
