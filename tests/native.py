import ctypes as c
import random
from pathlib import Path
k=c.CDLL(str(Path(__file__).resolve().parents[1]/'dist/libvlk.so'))
u32,u64,i32=c.c_uint32,c.c_uint64,c.c_int32
for name,args,ret in [('abi',[],u32),('spawn',[u32]*4,i32),('restore',[u32]*4+[u64,u32],i32),('fork',[i32],i32),('exit',[i32],i32),('observe',[i32,u64,u32],i32),('advance',[i32,u64,u64,u32],i32),('time',[i32],u64),('value',[],u32),('work',[],u32)]:
    f=getattr(k,'vk_'+name); f.argtypes=args; f.restype=ret
assert k.vk_abi()==1
rng=random.Random(341)
mask=2**32-1
for kind in (1,2):
    for _ in range(500):
        seed,a,b=(rng.getrandbits(32) for _ in range(3))
        t=rng.randrange(300); x=seed
        for i in range(t): x=(a*x+b if kind==1 else a*x*x+b)&mask
        p=k.vk_spawn(kind,seed,a,b); assert p>0
        assert k.vk_observe(p,t,300)==0 and k.vk_value()==x
        assert k.vk_time(p)==0
        assert k.vk_advance(p,0,t,300)==0 and k.vk_value()==x
        assert k.vk_time(p)==t
        assert k.vk_observe(p,0,300)==0 and k.vk_value()==seed
        q=k.vk_restore(kind,seed,a,b,t,300); assert q>0
        assert k.vk_observe(q,t,0)==0 and k.vk_value()==x
        assert k.vk_exit(q)==k.vk_exit(p)==0
print('native: 1000 seeded differential trajectories; observation, commit, rewind, restore')
p=k.vk_spawn(1,7,1,3); t=10**12
assert k.vk_advance(p,0,t,128)==0 and k.vk_value()==(7+3*t)&mask
assert k.vk_advance(p,0,t+1,128)==-3 and k.vk_time(p)==t
assert k.vk_advance(p,t,t-1,128)==-1
assert k.vk_advance(p,t,t+1,0)==-4 and k.vk_time(p)==t
assert k.vk_observe(p,2**64-1,128)==-1
q=k.vk_fork(p); assert q>0 and q!=p
assert k.vk_advance(q,t,t+1,1)==0 and k.vk_time(p)==t
assert k.vk_exit(q)==0 and k.vk_observe(q,t,128)==-1
assert k.vk_exit(p)==0
p=k.vk_spawn(2,1,1,1)
assert k.vk_advance(p,0,10,9)==-4 and k.vk_time(p)==0
assert k.vk_restore(2,1,1,1,10,9)==-4
assert k.vk_exit(p)==0
assert k.vk_spawn(99,0,0,0)==-1
ps=[k.vk_spawn(1,0,1,0) for _ in range(64)]
assert len(set(ps))==64 and min(ps)>0 and k.vk_spawn(1,0,1,0)==-2
assert k.vk_exit(ps[0])==0
r=k.vk_spawn(1,0,1,0); assert r>0 and r not in ps
assert k.vk_observe(ps[0],0,0)==-1
for p in ps[1:]+[r]: assert k.vk_exit(p)==0
print('native: lifecycle, capacity, stale handles, budget and conflict checks passed')
