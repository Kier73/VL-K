"""Pure guest observation and replay-checked continuation; no external effects."""
import argparse
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from guest import Guest, MASK
from loop_receipt import canonical, digest

MAX_TICK = (1 << 64)-1
DISPATCH_LIMIT = 100000
FILE_LIMIT = 1 << 20


def coordinate(n):
    if type(n) is not int or not 0 <= n <= MAX_TICK:
        raise ValueError('invalid logical coordinate')
    return n


def load_json(path):
    with open(path, 'rb') as f:
        data = f.read(FILE_LIMIT+1)
    if len(data)>FILE_LIMIT:
        raise ValueError('file too large')
    return json.loads(data)


def validate(program):
    if not isinstance(program, (tuple,list)) or not 1 <= len(program) <= 4096:
        raise ValueError('invalid program size')
    forms = {'set':('r','v'), 'mov':('r','r'), 'add':('r','r'), 'mul':('r','r'),
             'xor':('r','r'), 'and':('r','r'), 'jmp':('p',), 'jnz':('r','p'), 'halt':('r',)}
    limits = {'r':7,'v':MASK,'p':len(program)-1}
    result=[]
    for q in program:
        if not isinstance(q,(tuple,list)) or not q or type(q[0]) is not str or q[0] not in forms:
            raise ValueError('unsupported or effectful instruction')
        args=forms[q[0]]
        if len(q)!=len(args)+1 or any(type(v) is not int or not 0<=v<=limits[k] for k,v in zip(args,q[1:])):
            raise ValueError('invalid instruction operands')
        result.append(tuple(q))
    return tuple(result)


class Session:
    """Serialized owner of a pure guest; every committed state has a logical tick."""
    def __init__(self, program):
        self.program=validate(program)
        self.identity=digest(self.program)
        self._guest=Guest(self.program)
        self._tick=0

    @property
    def tick(self):
        return self._tick

    def _state(self,g,t):
        return {'tick':str(t),'pc':g.pc,'registers':g.r[:],'halted':g.halted,'status':g.status}

    def status(self):
        return self._state(self._guest,self.tick)

    def _realize(self, target, base=None):
        coordinate(target)
        g=Guest(self.program)
        start=0
        if base is not None:
            g.r=base.r[:];g.pc=base.pc;g.halted=base.halted;g.status=base.status;start=self.tick
        if target<start:
            raise ValueError('cannot advance backward')
        count=g.run(target-start,dispatch_budget=DISPATCH_LIMIT)
        if count!=target-start:
            raise RuntimeError('coordinate beyond halt or dispatch limit')
        return g

    def observe(self,target):
        return self._state(self._realize(target),target)

    def advance(self,expected,target):
        coordinate(expected)
        if expected!=self.tick:
            raise ValueError('stale coordinate')
        candidate=self._realize(target,self._guest)
        self._guest=candidate;self._tick=target
        return self.status()

    def checkpoint(self):
        state=self.status()
        if canonical(self.observe(self.tick))!=canonical(state):
            raise RuntimeError('state not reproducible from genesis')
        body={'version':1,'program_sha256':self.identity,'state':state}
        return {'body':body,'sha256':digest(body)}

    @classmethod
    def restore(cls,program,envelope):
        s=cls(program)
        try:
            body=envelope['body']
            if body['version']!=1 or body['program_sha256']!=s.identity or envelope['sha256']!=digest(body):
                raise ValueError('checkpoint identity mismatch')
            t=body['state']['tick']
            if type(t) is not str or not t.isascii() or not t.isdecimal() or len(t)>20 or str(int(t))!=t:
                raise ValueError('invalid tick encoding')
            s.advance(0,int(t))
            if canonical(s.checkpoint())!=canonical(envelope):
                raise ValueError('checkpoint mismatch')
        except (KeyError,TypeError,IndexError,OverflowError) as exc:
            raise ValueError('invalid checkpoint') from exc
        return s


def save(path,envelope):
    path=Path(path); name=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='ascii',dir=path.parent,delete=False) as f:
            name=f.name;f.write(canonical(envelope)+'\n');f.flush();os.fsync(f.fileno())
        os.replace(name,path);name=None
    finally:
        if name is not None: os.unlink(name)


def main():
    p=argparse.ArgumentParser(description='Inspect and navigate a pure guest program')
    p.add_argument('program');p.add_argument('--restore');a=p.parse_args()
    try:
        spec=load_json(a.program)
        if not isinstance(spec,dict) or set(spec)!={'program'}: raise ValueError('expected pure program document')
        s=Session.restore(spec['program'],load_json(a.restore)) if a.restore else Session(spec['program'])
    except (ValueError,TypeError,RuntimeError,OSError) as exc:
        print(f'debug: {exc}',file=sys.stderr);return 125
    for line in sys.stdin:
        try:
            q=shlex.split(line)
            if not q: continue
            if q==['quit']: return 0
            if q==['status']: result=s.status()
            elif len(q)==2 and q[0]=='step': result=s.advance(s.tick,s.tick+coordinate(int(q[1])))
            elif len(q)==2 and q[0]=='observe': result=s.observe(int(q[1]))
            elif len(q)==2 and q[0]=='save': save(q[1],s.checkpoint());result={'saved':q[1],'tick':str(s.tick)}
            else: raise ValueError('commands: status, step N, observe T, save PATH, quit')
            print(canonical(result),flush=True)
        except (ValueError,TypeError,RuntimeError,OSError) as exc:
            print(canonical({'error':str(exc)}),flush=True)
    return 0


if __name__=='__main__': sys.exit(main())
