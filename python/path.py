"""Exact ordered affine paths over u32; finite selector quotient when admissible."""
MASK = (1 << 32) - 1


def path_run(x, phase, cases, count, *, selector='clock', mode='auto', budget=1000000):
    if any(type(v) is not int or v < 0 for v in (x, phase, count, budget)) or x > MASK or count >= 1 << 64:
        raise ValueError('invalid state, count or budget')
    if selector not in ('clock', 'residue') or mode not in ('auto', 'reference', 'ground'):
        raise ValueError('invalid selector or mode')
    if not isinstance(cases, (tuple, list)) or not 1 <= len(cases) <= 4096:
        raise ValueError('invalid case table')
    m = len(cases)
    for row in cases:
        if len(row) != 3 or any(type(v) is not int for v in row) or not (0 <= row[0] <= MASK and 0 <= row[1] <= MASK and 0 <= row[2] < m):
            raise ValueError('invalid case')
    if phase >= m:
        raise ValueError('invalid phase')
    eligible = selector == 'clock' or m & (m - 1) == 0
    if selector == 'residue':
        phase = x % m
    if mode == 'ground' and not eligible:
        raise ValueError('selector has no admitted quotient')
    # Conservative worst-case charge: selector discovery, compositions, tail, powering.
    bound = 4*m + 2*count.bit_length() + 4
    use = eligible and (mode == 'ground' or (mode == 'auto' and count > bound))
    work = 0
    def charge(n=1):
        nonlocal work
        if work + n > budget:
            raise RuntimeError('path budget exhausted')
        work += n
    def next_phase(p):
        a,b,q = cases[p]
        return q if selector == 'clock' else (a*p+b) % m
    def compose(after, before):
        charge()
        a,b = after; c,d = before
        return (a*c & MASK, (a*d+b) & MASK)
    def apply(t, value):
        charge()
        return (t[0]*value+t[1]) & MASK
    if not use:
        for _ in range(count):
            charge(2)
            a,b,q = cases[phase]
            x = (a*x+b) & MASK
            phase = q if selector == 'clock' else x % m
        return x,phase,work,'reference'
    seen, order = {}, []
    while phase not in seen and len(order) < count:
        charge()
        seen[phase] = len(order); order.append(phase); phase = next_phase(phase)
    if len(order) == count:
        for p in order: x = apply(cases[p][:2],x)
        return x,phase,work,'ground'
    cut = seen[phase]
    for p in order[:cut]: x = apply(cases[p][:2],x)
    cycle = order[cut:]
    cycles, tail = divmod(count-cut,len(cycle))
    t = (1,0)
    for p in cycle: t = compose(cases[p][:2],t)
    while cycles:
        if cycles & 1: x = apply(t,x)
        cycles >>= 1
        if cycles: t = compose(t,t)
    for p in cycle[:tail]: x = apply(cases[p][:2],x)
    return x,cycle[tail],work,'ground'
