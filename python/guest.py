"""Small interactable guest ISA, using ordinary memory and explicit I/O effects."""
import argparse
import json
import sys
from memory import AddressSpace
from path import path_run, MASK
from lift import recognize, navigate


class Guest:
    def __init__(self, program, memory=None, *, mode='auto', input_stream=None, output_stream=None):
        self.program = tuple(tuple(i) for i in program)
        self.memory = AddressSpace() if memory is None else memory
        self.r = [0]*8
        self.pc = 0
        self.halted = False
        self.status = None
        self.mode = mode
        self.input = input_stream
        self.output = output_stream
        self.work = 0
        self.dispatches = 0
        self.lifted = 0
        self._loops = {}

    def run(self, budget, path_budget=1000000, *, dispatch_budget=None):
        if type(budget) is not int or budget < 0: raise ValueError('invalid guest budget')
        if dispatch_budget is not None and (type(dispatch_budget) is not int or dispatch_budget < 0): raise ValueError('invalid dispatch budget')
        start_dispatches = self.dispatches
        steps = 0
        def reg(i):
            if type(i) is not int or not 0 <= i < 8: raise ValueError('invalid register')
            return i
        def imm(i):
            if type(i) is not int or not 0 <= i <= MASK: raise ValueError('invalid immediate')
            return i
        def target(i):
            if type(i) is not int or not 0 <= i < len(self.program): raise ValueError('invalid branch')
            return i
        while not self.halted and steps < budget:
            if not 0 <= self.pc < len(self.program): raise ValueError('instruction fetch fault')
            if self.mode != 'reference' and self.program[self.pc] and self.program[self.pc][0]=='mov':
                if self.pc not in self._loops:
                    self._loops[self.pc] = recognize(self.program,self.pc)
                plan=self._loops[self.pc]
                jump=navigate(plan,self.r,budget-steps,path_budget) if plan else None
                if jump:
                    n,s,x,c,p,y,w,ticks,exit_pc=jump
                    self.r[s],self.r[x],self.r[c]=p,y,(self.r[c]-n)&MASK
                    if self.r[c]==0: self.pc=exit_pc
                    steps+=ticks; self.lifted+=ticks; self.work+=w; path_budget-=w
                    continue
            if dispatch_budget is not None and self.dispatches-start_dispatches >= dispatch_budget:
                break
            op,*a = self.program[self.pc]; pc = self.pc+1
            if op == 'set': d,v=a; self.r[reg(d)]=imm(v)
            elif op in ('mov','add','mul','xor','and'):
                d,s=map(reg,a); x,y=self.r[d],self.r[s]
                self.r[d]=({'mov':lambda:y,'add':lambda:x+y,'mul':lambda:x*y,'xor':lambda:x^y,'and':lambda:x&y}[op]()) & MASK
            elif op == 'load8': d,s=map(reg,a); self.r[d]=self.memory.read(self.r[s],1)[0]
            elif op == 'store8': d,s=map(reg,a); self.memory.write(self.r[d],bytes([self.r[s]&255]))
            elif op == 'jmp': pc=target(a[0])
            elif op == 'jnz':
                d,t=a; t=target(t)
                if self.r[reg(d)]: pc=t
            elif op == 'read':
                d=reg(a[0]); b=self.input.read(1); self.r[d]=b[0] if b else MASK
            elif op == 'write': self.output.write(bytes([self.r[reg(a[0])]&255]))
            elif op == 'repeat':
                d,p,n,cases,selector=a; d,p,n=map(reg,(d,p,n))
                if d==p or d==n or p==n: raise ValueError('repeat registers must be distinct')
                x,q,w,_=path_run(self.r[d],self.r[p],cases,self.r[n],selector=selector,mode=self.mode,budget=path_budget)
                self.r[d],self.r[p]=x,q; self.work+=w; path_budget-=w
            elif op == 'halt': self.status=self.r[reg(a[0])]&255; self.halted=True
            else: raise ValueError('unknown instruction')
            self.pc=pc;steps+=1;self.dispatches+=1
        return steps


def main():
    p=argparse.ArgumentParser();p.add_argument('program');p.add_argument('--budget',type=int,default=1000000)
    p.add_argument('--mode',choices=['auto','reference','ground'],default='auto');a=p.parse_args()
    try:
        with open(a.program,encoding='utf8') as f: spec=json.load(f)
        memory=AddressSpace()
        for m in spec.get('memory',[]): memory.map(m['start'],m['size'],pattern=bytes.fromhex(m.get('pattern','00')))
        g=Guest(spec['program'],memory,mode=a.mode,input_stream=sys.stdin.buffer,output_stream=sys.stdout.buffer)
        g.run(a.budget)
        if not g.halted: raise RuntimeError('instruction budget exhausted')
        return g.status
    except (ValueError,RuntimeError,MemoryError,PermissionError,OSError,TypeError,KeyError,IndexError) as e:
        print(f'guest: {e}',file=sys.stderr);return 125

if __name__=='__main__': sys.exit(main())
