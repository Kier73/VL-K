import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from process import Supervisor, PIPE

ENV = dict(os.environ, PATH=str(ROOT / 'dist') + os.pathsep + os.environ['PATH'])
ENV.pop('VLK_MODE', None)
ENV.pop('VLK_BUDGET', None)
FIB = str(ROOT / 'examples/fib.vlk')

with Supervisor(3) as s:
    with tempfile.TemporaryDirectory() as tmp:
        h = s.spawn([sys.executable, '-c', 'import sys,os; sys.stdout.buffer.write(sys.stdin.buffer.read()); print(os.getcwd(),file=sys.stderr); sys.exit(19)'], stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=tmp)
        data = bytes(range(256)) * 4096
        out, err = s.communicate(h, data, timeout=10)
        assert out == data and err == (tmp+'\n').encode() and s.wait(h)==19
        assert s.status(h).returncode==19
        s.release(h)
    a = s.spawn([FIB,'1000000000000'],stdout=PIPE,stderr=PIPE,env=ENV)
    b = s.spawn([sys.executable,'-c','print(6*7)'],stdout=PIPE,stderr=PIPE)
    c = s.spawn([sys.executable,'-c','import time; time.sleep(60)'])
    assert a != h and len({a,b,c})==3
    try:
        s.spawn(['true'])
        raise AssertionError('capacity not enforced')
    except RuntimeError: pass
    try:
        s.wait(c,timeout=0.01)
        raise AssertionError('timeout not enforced')
    except subprocess.TimeoutExpired: pass
    assert s.status(c).returncode is None
    try:
        s.release(c)
        raise AssertionError('released live child')
    except RuntimeError: pass
    assert s.communicate(a,timeout=10)==(b'1115770309 906757858\n',b'')
    assert s.communicate(b,timeout=10)==(b'42\n',b'')
    assert s.wait(a)==s.wait(b)==0
    s.terminate(c); assert s.wait(c,timeout=10)==-signal.SIGTERM
    for p in (a,b,c): s.release(p)
    try:
        s.status(a)
        raise AssertionError('stale handle accepted')
    except KeyError: pass
    try:
        s.spawn(['/nonexistent/vlk-process'])
        raise AssertionError('missing process accepted')
    except FileNotFoundError: pass
    child = s.spawn([sys.executable,'-c','import time; time.sleep(60)'])
    pid = s.status(child).pid
# A direct child must have been reaped, not left as a zombie.
try:
    os.waitpid(pid,os.WNOHANG)
    raise AssertionError('child not reaped')
except ChildProcessError: pass
try:
    s.spawn(['true'])
    raise AssertionError('closed table accepted spawn')
except RuntimeError: pass
print('K2 process supervisor: concurrent native/optimized processes, 1 MiB binary stream, wait, timeout, signal, capacity, stale handle, cleanup')
