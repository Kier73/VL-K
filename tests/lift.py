import io, random, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from guest import Guest
from path import MASK

# R0 state; R1 scratch; R2 counter; R3 mask; R4/R5 coefficients;
# R6 decrement; R7 alternate multiplier. Addition is common to both branches.
LOOP=[('mov',1,0),('and',1,3),('jnz',1,6),('mul',0,4),('add',0,5),('jmp',9),('mul',0,7),('add',0,5),('jmp',9),('add',2,6),('jnz',2,0),('write',0),('halt',1)]

def make(seed, mode, program=LOOP):
    g=Guest(program,mode=mode,output_stream=io.BytesIO());g.r[:]=seed;return g

def state(g):return (g.pc,g.r[:],g.halted,g.status,g.output.getvalue())

rng=random.Random(19271); lifted=0; checks=0
for _ in range(500):
    n=rng.randrange(1,1000);seed=[rng.getrandbits(32),rng.getrandbits(32),n,rng.choice([0,1,3,7,15,31,63]),rng.getrandbits(32),rng.getrandbits(32),MASK,rng.getrandbits(32)]
    a,b=make(seed,'auto'),make(seed,'reference')
    expected=seed[0];scratch=0
    for i in range(n):
        scratch=expected&seed[3];expected=(expected*(seed[7] if scratch else seed[4])+seed[5])%2**32
    while not b.halted:
        budget=rng.randrange(1,2000);assert a.run(budget)==b.run(budget);assert state(a)==state(b);checks+=1
    assert a.r[0]==expected and a.r[1]==scratch and a.r[2]==0
    lifted+=a.lifted
assert lifted>0
print('500 randomized programs;',checks,'identical budget checkpoints;',lifted,'lifted logical instructions')
# Counter zero is a do-while loop of 2^32 iterations. Known path alternates: even x -> x+1, odd x -> 3*x+1.
seed=[0,0,0,1,1,1,MASK,3];g=make(seed,'auto');n=2**32;assert g.run(n*8+2)==n*8+2 and g.halted
assert g.r[0]==(2*(pow(3,n//2,2**32)-1))&MASK and g.r[2]==0 and g.r[1]==1
assert g.dispatches==2 and g.lifted==n*8
print('zero-counter wrap:',n,'iterations;',g.dispatches,'ordinary dispatches;',g.work,'charged path work;',g.r[0])
# Noncontiguous bitmask, changed decrement, alias and effect in branch must not lift.
for seed,program in [([3,0,100,5,1,1,MASK,3],LOOP),([3,0,100,1,1,1,MASK-1,3],LOOP),([3,0,100,1,1,1,MASK,3],LOOP[:4]+[('add',0,2)]+LOOP[5:]),([3,0,100,1,1,1,MASK,3],LOOP[:4]+[('write',0),('jmp',9)]+LOOP[6:])]:
    a,b=make(seed,'auto',program),make(seed,'reference',program)
    assert a.run(802)==b.run(802) and state(a)==state(b) and a.lifted==0
# Low optimization budget falls back; guest instruction budget and outcomes unchanged.
a,b=make([0,0,100,1,1,1,MASK,3],'auto'),make([0,0,100,1,1,1,MASK,3],'reference')
assert a.run(802,path_budget=0)==b.run(802) and state(a)==state(b) and a.lifted==0
print('negative controls: irregular mask, decrement, alias, effects, optimization budget')
