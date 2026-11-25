"""Run a pinned, unmodified E-CPU utility against VL-K's independent evaluators."""
import hashlib
import importlib.util
import random
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from path import path_run
from vlk import Kernel

SOURCE_BLOB='cb1d4ba145c584c437bf38f17f2899d50f83728c'
source=Path(sys.argv[1])/'mailcpu/rrns.py'
raw=source.read_bytes()
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==SOURCE_BLOB
spec=importlib.util.spec_from_file_location('ecpu_pinned_rrns',source)
rrns=importlib.util.module_from_spec(spec);spec.loader.exec_module(rrns)

rng=random.Random(827);m=2**32;k=Kernel();mods=rrns.primes_below(1000,6)
assert len(mods)==6 and rrns.legit_range(mods,4)>m
for i in range(4096):
    a,b,x=(rng.getrandbits(32) for _ in range(3))
    n=rng.randrange(101) if i<2048 else rng.getrandbits(64)
    A,B=rrns.affine_orbit_jump(a,b,m,n);expected=(A*x+B)%m
    if i<2048:
        ref=x
        for _ in range(n):ref=(a*ref+b)%m
        assert ref==expected
    native=k.evaluate([x,0,0,0],[['mul',0,a],['add',0,b]],n)
    assert native['status']==0 and native['registers']==[expected,0,0,0]
    assert path_run(x,0,[(a,b,0)],n,mode='ground')[:2]==(expected,0)
    pairs=list(zip(mods,rrns.encode_rrns(expected,mods)));rng.shuffle(pairs)
    observed=pairs[:5]
    assert rrns.recover_rrns(observed,4,mods)==(expected,True)
    modulus,residue=observed[-1];observed[-1]=(modulus,(residue+1)%modulus)
    assert rrns.recover_rrns(observed,4,mods)==(expected,False)
# State-dependent branch selection, not one globally affine step.
for _ in range(1024):
    x=rng.getrandbits(31)*2;n=rng.getrandbits(64)
    A,B=rrns.affine_orbit_jump(3,4,m,n//2);expected=(A*x+B+n%2)%m
    r=path_run(x,0,[(1,1,0),(3,1,0)],n,selector='residue',mode='ground')
    assert r[:2]==(expected,n%2)
print('Pinned E-CPU RRNS:',SOURCE_BLOB)
print('4096 affine cases, 2048 direct iterations, 4096 shuffled residue recoveries, 4096 corruptions rejected, 1024 conditional paths')
