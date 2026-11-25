"""Portable pure-loop observation receipt; identity, not authentication."""
import hashlib
import json
from lift import recognize, navigate
from path import MASK


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('ascii')).hexdigest()


def issue(program, registers, pc, ticks, *, path_budget=1000000):
    if (type(pc) is not int or not 0<=pc<len(program) or type(ticks) is not int or not 0<=ticks<2**64
            or len(registers)!=8 or any(type(v) is not int or not 0<=v<=MASK for v in registers)
            or type(path_budget) is not int or path_budget<0):
        raise ValueError('invalid observation request')
    plan=recognize(program,pc)
    jump=navigate(plan,registers,ticks,path_budget) if plan else None
    if jump is None:
        raise ValueError('no admitted profitable loop jump')
    n,s,x,c,p,y,work,elapsed,exit_pc=jump
    state=list(registers);state[s],state[x],state[c]=p,y,(state[c]-n)&MASK
    body={'version':1,'program_sha256':digest(program),'initial':list(registers),'pc':pc,
          'requested_ticks':ticks,'path_budget':path_budget,'iterations':n,'elapsed':elapsed,
          'end_pc':exit_pc if state[c]==0 else pc,'registers':state,'work':work}
    return {'body':body,'sha256':digest(body)}


def verify(receipt, program, registers, pc, ticks, *, path_budget=1000000):
    """Re-derive using the exact recognized semantics, not the asserted state."""
    try:
        expected=issue(program,registers,pc,ticks,path_budget=path_budget)
        return canonical(receipt)==canonical(expected)
    except (ValueError,TypeError,IndexError,KeyError,OverflowError):
        return False
