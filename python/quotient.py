"""Discover smaller exact residue selectors by proving equality on residue classes."""
from dataclasses import dataclass
from path import MASK, path_run


@dataclass(frozen=True)
class Quotient:
    original_size: int
    cases: tuple
    checks: int

    def observe(self, x, count, *, budget=1000000):
        y, _, work, method = path_run(x, x%len(self.cases), self.cases, count,
                                     selector='residue', mode='ground', budget=budget)
        return y, y%self.original_size, work, method


def discover(cases):
    """Find the smallest power-of-two quotient among original-row representatives."""
    if not isinstance(cases,(list,tuple)) or not 1<=len(cases)<=4096 or len(cases)&(len(cases)-1):
        raise ValueError('power-of-two residue table required')
    m=len(cases)
    if any(not isinstance(row,(tuple,list)) or len(row)!=2 or any(type(v) is not int or not 0<=v<=MASK for v in row) for row in cases):
        raise ValueError('invalid affine map')
    checks=0; d=1
    while d<=m:
        for p,(a,b) in enumerate(cases):
            A,B=cases[p%d];da=a-A;db=b-B;checks+=1
            # All x=p+m*k. Equality is equivalent to vanishing constant and slope in k.
            if (da*m)&MASK or (da*p+db)&MASK: break
        else:
            return Quotient(m,tuple((a,b,0) for a,b in cases[:d]),checks)
        d*=2
    raise AssertionError('identity quotient must exist')


def main():
    """One admitted table, many observations; newline JSON requests on stdin."""
    import argparse
    import json
    import sys
    from debugger import load_json
    p=argparse.ArgumentParser();p.add_argument('table');a=p.parse_args()
    try:
        q=discover(load_json(a.table))
        print(json.dumps({'original_cases':q.original_size,'reduced_cases':len(q.cases),'checks':q.checks}),flush=True)
    except (ValueError,TypeError,OSError) as exc:
        print(f'ground: {exc}',file=sys.stderr);return 125
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if type(request) is not dict or set(request)!={'x','count'}:raise ValueError('expected x and count')
            count=request['count']
            if type(count) is not str or len(count)>20 or not count.isascii() or not count.isdecimal() or str(int(count))!=count:raise ValueError('invalid count')
            x=request['x']
            if type(x) is not int or not 0<=x<=MASK:raise ValueError('invalid x')
            y,p,w,method=q.observe(x,int(count));result={'x':y,'phase':p,'work':w,'method':method}
        except (ValueError,TypeError,RuntimeError) as exc:
            result={'error':str(exc)}
        print(json.dumps(result),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
