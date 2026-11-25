import os
import signal
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from process import Supervisor, PIPE, DEVNULL
ENV = dict(os.environ, PATH=str(ROOT/'dist')+os.pathsep+os.environ['PATH'])
ENV.pop('VLK_MODE', None)
ENV.pop('VLK_BUDGET', None)
FIB = str(ROOT/'examples/fib.vlk')
with Supervisor(4) as s:
    commands = [[FIB,'1000000000000'],['cut','-d',' ','-f','1']]
    hs = s.pipeline(commands, stdout=PIPE, env=ENV)
    assert s.communicate(hs[-1],timeout=10)==(b'1115770309\n',None)
    assert [s.wait(h,timeout=10) for h in hs]==[0,0]
    for h in hs: s.release(h)
    hs = s.pipeline([['yes','x'],['head','-c','1048576'],['wc','-c']],stdout=PIPE)
    assert int(s.communicate(hs[-1],timeout=10)[0])==1048576
    assert [s.wait(h,timeout=10) for h in hs]==[-signal.SIGPIPE,0,0]
    for h in hs: s.release(h)
    with tempfile.TemporaryFile() as f:
        hs=s.pipeline([['printf','abc'],['tr','a-z','A-Z']],stdout=f)
        assert [s.wait(h,timeout=10) for h in hs]==[0,0]
        f.seek(0); assert f.read()==b'ABC'
        for h in hs: s.release(h)
    before=len(os.listdir('/proc/self/fd'))
    for _ in range(20):
        try:
            s.pipeline([['sleep','60'],['/nonexistent/vlk-stage']],stdout=DEVNULL)
            raise AssertionError('failed stage accepted')
        except FileNotFoundError: pass
    assert len(os.listdir('/proc/self/fd'))==before
    hs=s.pipeline([['true']]*4,stdout=DEVNULL)
    assert [s.wait(h,timeout=10) for h in hs]==[0]*4
    for h in hs: s.release(h)
print('K2 pipeline: mixed execution, 1 MiB backpressure, SIGPIPE, file output, 20 failed-stage rollbacks without descriptor leaks')
