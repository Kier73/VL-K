"""A bounded test-only guest executes a checksum program through mapped memory."""
import random
import sys
import zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'python'))
from memory import AddressSpace

# Guest program: r0 pointer, r1 end, r2=a, r3=b, r4=byte.
PROGRAM=(('jge',0,1,8),('ld8',4,0),('add',2,4),('mod',2,65521),
         ('add',3,2),('mod',3,65521),('inc',0),('jmp',0),('halt',))


class Guest:
    def __init__(self, memory, start, size):
        self.memory=memory;self.r=[start,start+size,1,0,0];self.pc=0;self.halted=False

    def run(self, budget):
        steps=0
        while steps<budget and not self.halted:
            op,*a=PROGRAM[self.pc];self.pc+=1;steps+=1
            if op=='jge':
                if self.r[a[0]]>=self.r[a[1]]:self.pc=a[2]
            elif op=='ld8': self.r[a[0]]=self.memory.read(self.r[a[1]],1)[0]
            elif op=='add': self.r[a[0]]+=self.r[a[1]]
            elif op=='mod': self.r[a[0]]%=a[1]
            elif op=='inc': self.r[a[0]]+=1
            elif op=='jmp': self.pc=a[0]
            elif op=='halt': self.halted=True
        return steps

    def fork(self):
        child=Guest(self.memory.fork(),0,0);child.r=self.r[:];child.pc=self.pc;child.halted=self.halted;return child

    def checksum(self):
        assert self.halted
        return (self.r[3]<<16)|self.r[2]


rng=random.Random(743);size=1<<17;start=1<<42;pattern=rng.randbytes(509)
data=(pattern*((size+len(pattern)-1)//len(pattern)))[:size]
s=AddressSpace();s.map(start,size,pattern=pattern)
g=Guest(s,start,size);assert g.run(8*(size//2))==8*(size//2) and not g.halted
child=g.fork();patch=rng.randbytes(4097);offset=size//2+111
child.memory.write(start+offset,patch)
child_data=data[:offset]+patch+data[offset+len(patch):]
steps=0
while not (g.halted and child.halted):
    steps+=g.run(rng.randrange(1,30000));steps+=child.run(rng.randrange(1,30000))
assert g.checksum()==zlib.adler32(data)
assert child.checksum()==zlib.adler32(child_data)
assert g.checksum()!=child.checksum()
assert steps==8*size+4
print('Guest checksum:',size,'bytes per path;',steps+8*(size//2),'instructions including shared prefix;',hex(g.checksum()),hex(child.checksum()),'match independent zlib')
