import io
import random
import sys
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from path import path_run, MASK
from guest import Guest
from memory import AddressSpace

rng=random.Random(763)
for selector in ('clock','residue'):
    for _ in range(1500):
        m=rng.choice([1,2,4,8,16,32]); cases=[(rng.getrandbits(32),rng.getrandbits(32),rng.randrange(m)) for j in range(m)]
        x=rng.getrandbits(32);p=rng.randrange(m);n=rng.randrange(400)
        a=x;q=p if selector=='clock' else x%m
        for j in range(n):
            mul,add,nxt=cases[q];a=(mul*a+add)%2**32;q=nxt if selector=='clock' else a%m
        for mode in ('reference','ground','auto'):
            assert path_run(x,p,cases,n,selector=selector,mode=mode)[:2]==(a,q)
print('3000 independent randomized layered paths, 3 modes')
# Noncommuting maps with a transient selector and a length-2 cycle.
cases=[(1,7,1),(3,0,2),(1,2,1)]
n=10**12; result=path_run(5,0,cases,n)
# Independent closed form: after transient x=12; each (3x)+2 pair, x+1 triples.
k=(n-1)//2; a=(13*pow(3,k,2**32)-1)&MASK
if (n-1)%2:a=3*a&MASK
assert result[:2]==(a,2) and result[3]=='ground';print('trillion clock path',result)
# State-selected branch: quotient closed under u32 wrap; a non-power-of-two modulus is not admitted.
cases=[(1,1,0),(3,1,0),(1,3,0),(5,1,0)]
res=path_run(0,0,cases,10**12,selector='residue')
assert res[:2]==((2*(pow(3,5*10**11,2**32)-1))&MASK,0) and res[3]=='ground'
print('trillion residue path',res)
# Wrap changes the residue for m=3; a naive quotient would choose the wrong second map.
assert path_run(MASK,0,[(1,1,0),(1,9,0),(1,1,0)],2,selector='residue')[:2]==(1,1)
try:path_run(0,0,cases[:3],100,selector='residue',mode='ground');raise AssertionError('bad quotient admitted')
except ValueError:pass
assert path_run(0,0,cases[:3],100,selector='residue')[3]=='reference'
try:path_run(5,0,[(1,1,0)],10**12,budget=1);raise AssertionError('budget bypass')
except RuntimeError:pass
# General guest: reads ordinary input, transforms each byte with XOR, writes it to memory and stdout, exits on EOF.
program=[('set',1,255),('set',2,100),('set',3,1),('set',4,MASK),('read',0),('mov',5,0),('xor',5,4),('jnz',5,9),('halt',6),('xor',0,1),('store8',2,0),('load8',5,2),('write',5),('add',2,3),('jmp',4)]
data=rng.randbytes(16384);s=AddressSpace();s.map(100,len(data));out=io.BytesIO();g=Guest(program,s,input_stream=io.BytesIO(data),output_stream=out)
steps=0
while not g.halted:steps+=g.run(rng.randrange(1,1000))
expected=bytes(v^255 for v in data);assert out.getvalue()==s.read(100,len(data))==expected and g.status==0
# One ordinary repeated conditional block, backend mode invisible at output boundary.
program=[('set',0,5),('set',1,0),('set',2,10000),('repeat',0,1,2,[(1,7,1),(3,0,2),(1,2,1)],'clock'),('write',0),('halt',3)]
outputs=[]
for mode in ('reference','ground','auto'):
    out=io.BytesIO();g=Guest(program,mode=mode,output_stream=out);assert g.run(100)==6 and g.halted;outputs.append((out.getvalue(),g.r[:],g.status));print(mode,'guest path work',g.work)
assert outputs[0]==outputs[1]==outputs[2]
print('guest binary stream, memory, branch and exit:',steps,'instructions')

# Real CLI execution: binary streams through the native launcher.
root=Path(__file__).resolve().parents[1]
p=subprocess.run([str(root/'dist/vlk'),'guest',str(root/'examples/guest-echo.json')],input=data,capture_output=True,timeout=10)
assert (p.returncode,p.stdout,p.stderr)==(0,data,b'')
p=subprocess.run([str(root/'dist/vlk'),'guest',str(root/'examples/guest-echo.json'),'--budget','1'],input=data,capture_output=True,timeout=10)
assert p.returncode==125 and b'budget exhausted' in p.stderr
print('guest CLI: binary echo and instruction budget')
