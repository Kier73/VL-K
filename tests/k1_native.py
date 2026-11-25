import random, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from vlk import Kernel
k=Kernel(); rng=random.Random(371); mask=2**32-1
for _ in range(2000):
    seed=[rng.getrandbits(32) for _ in range(4)]; s=seed[:]; t=rng.randrange(100)
    ops=[]
    for j in range(rng.randrange(1,33)):
        op=rng.choice(['set','copy','add','mul','addr']); d=rng.randrange(4); x=rng.randrange(4) if op in ('copy','addr') else rng.getrandbits(32); ops.append((op,d,x))
    for j in range(t):
        for op,d,x in ops:
            if op=='set': s[d]=x
            elif op=='copy': s[d]=s[x]
            elif op=='add': s[d]=(s[d]+x)&mask
            elif op=='mul': s[d]=(s[d]*x)&mask
            else: s[d]=(s[d]+s[x])&mask
    for mode in ('auto','ground','reference'):
        r=k.evaluate(seed,ops,t,mode=mode); assert r['status']==0 and r['registers']==s
assert k.evaluate([2,3,0,0],[('mulr',0,1)],5)['registers']==[486,3,0,0]
assert k.evaluate([2,3,0,0],[('mulr',0,1)],5,budget=4)['status']==-4
assert k.evaluate([0,1,0,0],[('addr',0,1),('addr',1,0)],10**12)['registers']==[1115770309,906757858,0,0]
print('K1 native: 2000 random programs, 3 modes, nonlinear and trillion-block checks')
