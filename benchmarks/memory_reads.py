"""Measure dense read costs with identical queries and independently checked digests."""
import hashlib
import mmap
import random
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'python'))
from memory import Memory

size=16<<20; p=b'abcde'; source=(p*((size+4)//5))[:size]
rng=random.Random(42); queries=[rng.randrange(size-64) for _ in range(30000)]
expected=hashlib.sha256(b''.join(source[i:i+64] for i in queries)).digest()
with mmap.mmap(-1,size) as mm:
    mm[:]=source
    resident=Memory(size,data=source); structural=Memory(size,pattern=p)
    methods={'mmap':lambda i:mm[i:i+64], 'resident':lambda i:resident.read(i,64), 'periodic':lambda i:structural.read(i,64)}
    times={k:[] for k in methods}
    for _ in range(5):
        order=list(methods);rng.shuffle(order)
        for name in order:
            h=hashlib.sha256();read=methods[name];t=time.perf_counter()
            for i in queries:h.update(read(i))
            times[name].append(1000*(time.perf_counter()-t));assert h.digest()==expected
    for name, samples in times.items(): print(name, 'median_ms',round(statistics.median(samples),2),'samples_ms',[round(t,2) for t in samples])
print('digest',expected.hex(),'logical_bytes',size,'reads',len(queries),'bytes_per_read',64)
print('Timing excludes mapping construction, includes loop and hash; not a universal speedup claim.')
