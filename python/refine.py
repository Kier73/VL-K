"""Constructive refinement of weighted residue laws into translation + sparse clock."""
from collections import Counter
from dataclasses import dataclass
from math import gcd
from path import MASK
from weighted_ground import discover_weighted


@dataclass(frozen=True)
class SparseClock:
    original_size: int
    stride: int
    default: int
    exceptions: tuple

    def observe(self, x, ticks, maximum, *, budget=1000000):
        if any(type(v) is not int or v < 0 for v in (x,ticks,maximum,budget)) or x>MASK or max(ticks,maximum)>=2**64:
            raise ValueError('invalid coordinate or budget')
        work=0
        def charge(n=1):
            nonlocal work
            if work+n>budget: raise RuntimeError('sparse clock budget exhausted')
            work+=n
        def rank(values, key, inclusive=False):
            lo,hi=0,len(values)
            while lo<hi:
                charge();mid=(lo+hi)//2
                if values[mid]<key or (inclusive and values[mid]==key):lo=mid+1
                else:hi=mid
            return lo
        if not maximum or ticks==0:return x,0,0,None,work
        m=self.original_size;g=gcd(self.stride,m);period=m//g
        inv=pow(self.stride//g,-1,period) if period>1 else 0
        charge(2) # gcd and modular inverse (bounded selector words)
        events=[]
        for residue,weight in self.exceptions:
            charge();delta=(residue-x)%m
            if delta%g==0:events.append(((delta//g*inv)%period,weight))
        events.sort()
        offsets=[];ends=[];prefix=[0]
        for i,w in events:
            charge();offsets.append(i);ends.append(self.default*i+prefix[-1]+w)
            prefix.append(prefix[-1]+w-self.default)
        duration=self.default*period+prefix[-1]
        charge();cycles,remaining=divmod(ticks,duration)
        completed=rank(ends,remaining,True)
        tail=(remaining-prefix[completed])//self.default
        if completed<len(offsets):tail=min(tail,offsets[completed])
        n=min(maximum,cycles*period+tail)
        charge();q,r=divmod(n,period)
        elapsed=self.default*n+q*prefix[-1]+prefix[rank(offsets,r)]
        charge();return (x+n*self.stride)&MASK,n,elapsed,(x+(n-1)*self.stride)%m if n else None,work


@dataclass(frozen=True)
class Refinement:
    ground: object
    checks: int
    reason: str
    witness: tuple | None = None


def refine(rows):
    """Check a synthesized global affine law, then factor a sparse temporal exception set.

    Refusal retains the previous exact dense representation. Not a universal minimizer.
    """
    if not isinstance(rows,(tuple,list)) or not 1<=len(rows)<=4096 or len(rows)&(len(rows)-1):
        raise ValueError('power-of-two selector required')
    if any(not isinstance(r,(list,tuple)) or len(r)!=3 or any(type(v) is not int for v in r) or not (0<=r[0]<=MASK and 0<=r[1]<=MASK and 1<=r[2]<=65536) for r in rows):
        raise ValueError('invalid weighted map')
    m=len(rows);B=rows[0][1];A=(rows[1][0]+rows[1][1]-B)&MASK if m>1 else rows[0][0]
    checks=0
    for p,(a,b,w) in enumerate(rows):
        checks+=1
        if ((a-A)*p+b-B)&MASK: x=p
        elif ((a-A)*m)&MASK: x=p+m
        else:continue
        full=discover_weighted(rows)
        return Refinement(full,checks+full.checks,'state law differs',(x,(a*x+b)&MASK,(A*x+B)&MASK))
    if A!=1:
        full=discover_weighted(rows)
        return Refinement(full,checks+full.checks,'nontranslation state law')
    default=min(Counter(r[2] for r in rows).items(),key=lambda kv:(-kv[1],kv[0]))[0]
    exceptions=tuple((p,r[2]) for p,r in enumerate(rows) if r[2]!=default)
    if len(exceptions)>m//8:
        full=discover_weighted(rows)
        return Refinement(full,checks+full.checks,'dense exceptions')
    return Refinement(SparseClock(m,B,default,exceptions),checks,'translation and sparse duration')


def main():
    import argparse,json,sys
    from debugger import load_json
    p=argparse.ArgumentParser();p.add_argument('table');a=p.parse_args()
    try:
        r=refine(load_json(a.table));g=r.ground
        print(json.dumps({'method':type(g).__name__,'checks':r.checks,'reason':r.reason,'witness':r.witness,'exceptions':len(g.exceptions) if isinstance(g,SparseClock) else None}),flush=True)
    except (ValueError,TypeError,OSError) as exc:p.exit(125,f'refine: {exc}\n')
    for line in sys.stdin:
        try:
            q=json.loads(line)
            if type(q) is not dict or set(q)!={'x','ticks','maximum'}:raise ValueError('expected x, ticks, maximum')
            def integer(v):
                if type(v) is not str or not v.isascii() or not v.isdecimal() or len(v)>20 or str(int(v))!=v:raise ValueError('invalid coordinate')
                return int(v)
            y,n,t,last,w=g.observe(q['x'],integer(q['ticks']),integer(q['maximum']))
            result={'x':y,'iterations':str(n),'elapsed':str(t),'last':last,'work':w}
        except (ValueError,TypeError,RuntimeError) as exc:result={'error':str(exc)}
        print(json.dumps(result),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
