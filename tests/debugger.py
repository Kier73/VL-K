import copy
import json
import os
import random
import select
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from debugger import Session
from loop_receipt import digest
from process import Supervisor, PIPE

program=json.loads((ROOT/'examples/guest-debug.json').read_text())['program']
MASK=2**32-1
pairs=2**31
cut=7+15*(pairs-1)+7+4
end=7+15*pairs+1
x=2*(pow(3,pairs-1,2**32)-1)&MASK
expected={'tick':str(cut),'pc':13,'registers':[3*(x+1)&MASK,1,1,1,1,1,MASK,3],'halted':False,'status':None}
s=Session(program);assert s.observe(cut)==expected and s.tick==0
assert s.advance(0,cut)==expected
before=s.status();cp=s.checkpoint()
for key in ('registers','pc','status'):
    # changed state with valid envelope hash still cannot authorize restore
    bad=copy.deepcopy(cp)
    if key=='registers':bad['body']['state'][key][0]^=1
    else:bad['body']['state'][key]=0
    bad['sha256']=digest(bad['body'])
    try:Session.restore(program,bad);raise AssertionError('tampering accepted')
    except ValueError:pass
for target in (cut-1,end+1):
    try:s.advance(cut,target);raise AssertionError('bad coordinate accepted')
    except (ValueError,RuntimeError):pass
    assert s.status()==before
try:s.advance(0,end);raise AssertionError('stale commit')
except ValueError:pass
assert s.status()==before
assert Session.restore(program,cp).advance(cut,end)['registers'][0]==2*(pow(3,pairs,2**32)-1)&MASK
try:Session([['write',0]]);raise AssertionError('effect admitted')
except ValueError:pass
q=Session([['jmp',0]])
try:q.advance(0,100001);raise AssertionError('dispatch cap bypass')
except RuntimeError:pass
assert q.tick==0

# Independent ordinary instruction evaluator: no Guest, recognizer, or path evaluator.
def oracle(code,n):
    r=[0]*8;pc=0;halt=False;status=None
    for _ in range(n):
        op,*a=code[pc];pc+=1
        if op=='set':r[a[0]]=a[1]
        elif op=='mov':r[a[0]]=r[a[1]]
        elif op=='and':r[a[0]]&=r[a[1]]
        elif op=='add':r[a[0]]=(r[a[0]]+r[a[1]])%2**32
        elif op=='mul':r[a[0]]=(r[a[0]]*r[a[1]])%2**32
        elif op=='jmp':pc=a[0]
        elif op=='jnz' and r[a[0]]:pc=a[1]
        elif op=='halt':halt=True;status=r[a[0]]%256
    return {'tick':str(n),'pc':pc,'registers':r,'halted':halt,'status':status}
rng=random.Random(741)
for _ in range(200):
    n=rng.randrange(500,2000);a=rng.randrange(0,n);code=copy.deepcopy(program)
    code[0][2]=rng.getrandbits(32);code[4][2]=rng.getrandbits(32);code[6][2]=rng.getrandbits(32)
    v=Session(code);assert v.advance(0,a)==oracle(code,a)
    restored=Session.restore(code,json.loads(json.dumps(v.checkpoint())))
    assert restored.advance(a,n)==oracle(code,n)
print('200 randomized checkpoints and continuations against independent interpreter; distant exact state; invalid/effect/dispatch rejection')

# A real child is killed after atomic checkpoint publication. Fresh process resumes.
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'checkpoint.json';cmd=[str(ROOT/'dist/vlk'),'debug',str(ROOT/'examples/guest-debug.json')]
    p=subprocess.Popen(cmd,stdin=PIPE,stdout=PIPE,stderr=PIPE,text=True)
    def send(line):
        p.stdin.write(line+'\n');p.stdin.flush()
        if not select.select([p.stdout],[],[],10)[0]:raise TimeoutError(line)
        return json.loads(p.stdout.readline())
    try:
        assert send(f'observe {cut}')==expected;assert send('status')['tick']=='0'
        assert send(f'step {cut}')==expected
        assert send(f'save {path}')['tick']==str(cut)
    finally:
        p.kill();p.communicate(timeout=10)
    assert p.returncode==-9
    size=path.stat().st_size
    with Supervisor() as sup:
        h=sup.spawn(cmd+['--restore',str(path)],stdin=PIPE,stdout=PIPE,stderr=PIPE)
        out,err=sup.communicate(h,f'status\nstep {end-cut}\nquit\n'.encode(),timeout=10)
        assert sup.wait(h)==0 and not err
        states=[json.loads(line) for line in out.splitlines()]
        assert states[0]==expected and states[1]['halted'] and states[1]['tick']==str(end)
        assert states[1]['registers'][0]==2*(pow(3,pairs,2**32)-1)&MASK
    print('hard-kill handoff:',cut,'->',end,'ticks;',size,'checkpoint bytes;',states[1])
