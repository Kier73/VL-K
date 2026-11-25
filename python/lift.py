"""Recognize pure bit-selected affine countdown loops, including unequal paths."""
from path import MASK, path_run


def recognize(program, start):
    def ins(i, op, n):
        if not 0 <= i < len(program):
            return None
        q = program[i]
        return q if len(q)==n and q[0]==op and all(type(v) is int for v in q[1:]) else None
    a,b,c = ins(start,'mov',3),ins(start+1,'and',3),ins(start+2,'jnz',3)
    if not a or not b or not c:
        return None
    _,s,x=a; _,sd,mask=b; _,st,branch=c
    if not s==sd==st or not start+4 <= branch <= min(start+67,len(program)-1):
        return None
    def arm(first, stop):
        body=[]
        for i in range(first,stop):
            j=ins(i,'jmp',2)
            if j:
                return tuple(body),i,j[1]
            q=ins(i,'mul',3) or ins(i,'add',3)
            if not q or q[1]!=x:
                return None
            body.append((q[0],q[2]))
        return None
    left=arm(start+3,branch)
    if not left or left[1]!=branch-1:
        return None
    tail=left[2]
    if not branch+1 <= tail <= min(branch+65,len(program)-2):
        return None
    right=arm(branch,tail)
    if not right or right[1]!=tail-1 or right[2]!=tail:
        return None
    a,b=ins(tail,'add',3),ins(tail+1,'jnz',3)
    if not a or not b:
        return None
    _,counter,dec=a; _,ct,back=b
    if counter!=ct or back!=start:
        return None
    modified={s,x,counter}; constants={mask,dec}|{r for body in (left[0],right[0]) for _,r in body}
    if len(modified)!=3 or modified & constants or any(not 0<=v<8 for v in modified|constants):
        return None
    return s,x,counter,mask,dec,left[0],right[0],tail+2


def navigate(plan, registers, remaining, path_budget):
    s,x,c,mask,dec,left,right,exit_pc=plan
    m=registers[mask]+1
    if m>4096 or m & (m-1) or registers[dec]!=MASK:
        return None
    maximum=registers[c] or 2**32
    lengths=(6+len(left),6+len(right))
    upper=min(maximum,remaining//min(lengths))
    if upper<=4*m+2*upper.bit_length()+4 or path_budget < m+len(left)+len(right)+1:
        return None
    def affine(body):
        a,b=1,0
        for op,r in body:
            v=registers[r]
            if op=='mul': a,b=a*v&MASK,b*v&MASK
            else: b=(b+v)&MASK
        return a,b,0
    maps=(affine(left),affine(right))
    cases=[maps[0]]+[maps[1]]*(m-1)
    work=m+len(left)+len(right)+1
    # Find the selector orbit and its weighted prefix; do not consume a partial arm.
    p=registers[x]%m; seen={}; times=[0]
    while p not in seen and len(seen)<maximum:
        length=lengths[bool(p)]
        if times[-1]+length>remaining:
            break
        if work>=path_budget:
            return None
        work+=1; seen[p]=len(seen); times.append(times[-1]+length)
        a,b,_=cases[p];p=(a*p+b)%m
    n=len(seen); ticks=times[-1]
    if p in seen and n<maximum:
        cut=seen[p]; period=n-cut; duration=ticks-times[cut]
        cycles=min((maximum-cut)//period,(remaining-times[cut])//duration)
        n=cut+cycles*period; ticks=times[cut]+cycles*duration
        for i in range(period):
            length=times[cut+i+1]-times[cut+i]
            if n==maximum or ticks+length>remaining: break
            if work>=path_budget: return None
            work+=1;n+=1;ticks+=length
    if n<=4*m+2*n.bit_length()+4:
        return None
    # Preserve last pre-transition selector, which is still in the scratch register.
    try:
        y,p,w,_=path_run(registers[x],registers[x]%m,cases,n-1,selector='residue',mode='ground',budget=path_budget-work)
    except RuntimeError:
        return None
    a,b,_=cases[p]
    return n,s,x,c,p,(a*y+b)&MASK,w+work,ticks,exit_pc
