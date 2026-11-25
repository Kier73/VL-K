"""Exact selector reduction preserving state AND additive logical time."""
from dataclasses import dataclass
from path import MASK, path_run


@dataclass(frozen=True)
class WeightedGround:
    original_size: int
    rows: tuple
    checks: int

    def observe(self, x, ticks, maximum, *, budget=1000000):
        """Maximal complete-iteration prefix; no claim about partial instruction state."""
        if any(type(v) is not int or v < 0 for v in (x,ticks,maximum,budget)) or x>MASK or maximum>=2**64 or ticks>=2**64:
            raise ValueError('invalid coordinate or budget')
        m=len(self.rows); p=x%m; seen={}; times=[0]; work=0
        def charge():
            nonlocal work
            if work>=budget: raise RuntimeError('weighted budget exhausted')
            work+=1
        while p not in seen and len(seen)<maximum:
            a,b,w=self.rows[p]
            if times[-1]+w>ticks: break
            charge();seen[p]=len(seen);times.append(times[-1]+w);p=(a*p+b)%m
        n=len(seen); elapsed=times[-1]
        if p in seen and n<maximum:
            cut=seen[p]; period=n-cut; duration=elapsed-times[cut]
            cycles=min((maximum-cut)//period,(ticks-times[cut])//duration)
            n=cut+cycles*period;elapsed=times[cut]+cycles*duration
            for i in range(period):
                w=times[cut+i+1]-times[cut+i]
                if n==maximum or elapsed+w>ticks: break
                charge();n+=1;elapsed+=w
        if not n: return x,0,0,None,work
        # Realize n-1, so the original last pre-transition residue is observable.
        cases=tuple((a,b,0) for a,b,_ in self.rows)
        y,p,w,_=path_run(x,x%m,cases,n-1,selector='residue',mode='ground',budget=budget-work)
        work+=w;charge();a,b,_=self.rows[p]
        return (a*y+b)&MASK,n,elapsed,y%self.original_size,work


def discover_weighted(rows):
    """Smallest representative quotient preserving affine maps and per-step weights."""
    if not isinstance(rows,(tuple,list)) or not 1<=len(rows)<=4096 or len(rows)&(len(rows)-1):
        raise ValueError('power-of-two selector required')
    if any(not isinstance(r,(list,tuple)) or len(r)!=3 or any(type(v) is not int for v in r) or not (0<=r[0]<=MASK and 0<=r[1]<=MASK and 1<=r[2]<=65536) for r in rows):
        raise ValueError('invalid weighted map')
    m=len(rows);checks=0;d=1
    while d<=m:
        for p,(a,b,w) in enumerate(rows):
            A,B,W=rows[p%d];checks+=1
            if w!=W or ((a-A)*m)&MASK or ((a-A)*p+b-B)&MASK: break
        else: return WeightedGround(m,tuple(tuple(r) for r in rows[:d]),checks)
        d*=2
    raise AssertionError('identity quotient must exist')
