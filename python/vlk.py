"""Dependency-free JSON/ctypes interface to the K1 kernel (serialized calls)."""
import ctypes as C
import json
import sys
from pathlib import Path
from threading import Lock

_LOCK = Lock()
OPS = {'set': 1, 'copy': 2, 'add': 3, 'mul': 4, 'addr': 5, 'mulr': 6}
MODES = {'auto': 0, 'reference': 1, 'ground': 2}

def uint(value, bits):
    if type(value) is not int or not 0 <= value < 2**bits:
        raise ValueError(f'expected unsigned {bits}-bit integer')
    return value

class Kernel:
    def __init__(self, library=None):
        self.k = C.CDLL(str(Path(library).resolve() if library else Path(__file__).resolve().parents[1] / 'dist/libvlk.so'))
        u, q, i = C.c_uint32, C.c_uint64, C.c_int32
        for name, args, ret in [('begin', [], None), ('seed', [u,u], i), ('append', [u,u,u], i), ('run', [q,u,u], i), ('result', [u], u), ('method', [], u), ('work', [], u)]:
            f = getattr(self.k, 'vk1_'+name); f.argtypes=args; f.restype=ret

    def evaluate(self, seed, program, steps, budget=100000, mode='auto'):
        if len(seed)!=4 or len(program)>64 or mode not in MODES:
            raise ValueError('expected 4 registers, at most 64 instructions, valid mode')
        seed = [uint(x,32) for x in seed]
        ops = [(OPS[op], uint(d,2), uint(x,2 if op in ('copy','addr','mulr') else 32)) for op,d,x in program]
        steps, budget = uint(steps,64), uint(budget,32)
        with _LOCK:
            self.k.vk1_begin()
            for r,v in enumerate(seed):
                if self.k.vk1_seed(r,v)!=0: raise RuntimeError('seed rejected')
            for op in ops:
                if self.k.vk1_append(*op)!=0: raise RuntimeError('instruction rejected')
            status = self.k.vk1_run(steps,budget,MODES[mode])
            return {'status':status, 'registers':[self.k.vk1_result(r) for r in range(4)] if status==0 else None, 'method': ['identity','reference','ground'][self.k.vk1_method()] if status==0 else None, 'work':self.k.vk1_work()}

if __name__=='__main__':
    try:
        result=Kernel().evaluate(**json.load(sys.stdin)); print(json.dumps(result)); sys.exit(0 if result['status']==0 else 1)
    except (ValueError, KeyError, TypeError, OSError) as e:
        print(json.dumps({'error':str(e)})); sys.exit(2)
