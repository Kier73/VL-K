"""Recognize a pure, equal-length, bit-selected affine countdown loop."""
from path import MASK, path_run


def recognize(program, start):
    # Two branches each contain mul/add/jmp, followed by decrement/backedge.
    b = program[start:start+11]
    if len(b) != 11:
        return None
    ops = ('mov','and','jnz','mul','add','jmp','mul','add','jmp','add','jnz')
    lengths = (3,3,3,3,3,2,3,3,2,3,3)
    if any(len(q)!=n or q[0]!=op or any(type(v) is not int for v in q[1:]) for q,n,op in zip(b,lengths,ops)):
        return None
    _,s,x=b[0]; _,sd,mask=b[1]; _,st,branch=b[2]
    _,x0,a0=b[3]; _,x1,b0=b[4]; _,j0=b[5]
    _,x2,a1=b[6]; _,x3,b1=b[7]; _,j1=b[8]
    _,counter,dec=b[9]; _,ct,back=b[10]
    if not (s==sd==st and x==x0==x1==x2==x3 and counter==ct and branch==start+6 and j0==j1==start+9 and back==start):
        return None
    modified={s,x,counter}; constants={mask,a0,b0,a1,b1,dec}
    if len(modified)!=3 or modified & constants or any(not 0<=v<8 for v in modified|constants):
        return None
    return s,x,counter,mask,a0,b0,a1,b1,dec


def navigate(plan, registers, remaining, path_budget):
    s,x,c,mask,a0,b0,a1,b1,dec=plan
    m=registers[mask]+1
    if m>4096 or m & (m-1) or registers[dec]!=MASK:
        return None
    n=min(registers[c] or 2**32,remaining//8)
    # Require a conservative advantage; validation/setup charged separately.
    if n<=4*m+2*n.bit_length()+4:
        return None
    cases=[(registers[a0],registers[b0],0)]+[(registers[a1],registers[b1],0)]*(m-1)
    # Last pre-transition residue is observable in the scratch register.
    if path_budget < m+1:
        return None
    try:
        y,p,w,_=path_run(registers[x],registers[x]%m,cases,n-1,selector='residue',mode='ground',budget=path_budget-m-1)
    except RuntimeError:
        return None
    a,b,_=cases[p]
    return n,s,x,c,p,(a*y+b)&MASK,w+m+1
