"""Exercise the real CLI under the VL-K supervisor; compare identical bytes and independent oracle."""
import statistics, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from process import Supervisor, PIPE
n=200000
expected=bytes([(2*(pow(3,n//2,2**32)-1))&255])
results={'reference':[],'auto':[]}
with Supervisor() as s:
    for order in [('reference','auto'),('auto','reference'),('reference','auto')]:
        for mode in order:
            t=time.perf_counter()
            p=s.spawn([str(ROOT/'dist/vlk'),'guest',str(ROOT/'examples/guest-conditional.json'),'--mode',mode,'--budget',str(n*8+9)],stdout=PIPE,stderr=PIPE)
            out,err=s.communicate(p,timeout=30);status=s.wait(p);s.release(p)
            results[mode].append(time.perf_counter()-t)
            assert (status,out,err)==(0,expected,b'')
for mode,ts in results.items():print(mode,'median seconds',round(statistics.median(ts),6),'samples',ts)
print('logical instructions',n*8+9,'verified stdout hex',expected.hex())
