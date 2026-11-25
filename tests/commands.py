import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VLK = str(ROOT / 'dist/vlk')
FIB = str(ROOT / 'examples/fib.vlk')
ENV = dict(os.environ, PATH=str(ROOT / 'dist')+os.pathsep+os.environ['PATH'])
ENV.pop('VLK_MODE', None)
ENV.pop('VLK_BUDGET', None)


def run(args, **kwargs):
    return subprocess.run(args, timeout=15, capture_output=True, env=kwargs.pop('env', ENV), **kwargs)


def signature(p):
    return p.returncode, p.stdout, p.stderr


with tempfile.TemporaryDirectory() as tmp:
    env = dict(ENV, VLK_TEST='value with spaces')
    child = [sys.executable, '-c', 'import os,sys; print(os.getcwd()); print(os.environ["VLK_TEST"]); print(repr(sys.argv[1:])); sys.stdout.buffer.write(sys.stdin.buffer.read()); print("err",file=sys.stderr); sys.exit(23)', 'literal; not shell', '']
    kwargs = dict(cwd=tmp, env=env, input=b'input\x00\xff\n')
    assert signature(run(child, **kwargs)) == signature(run([VLK,'run',*child], **kwargs))
    shell = ['-c', 'printf "beta\\nalpha\\n" > input; sort < input | tr a-z A-Z; exit 7']
    assert signature(run(['/bin/sh',*shell],cwd=tmp)) == signature(run([VLK,'shell',*shell],cwd=tmp))
    assert Path(tmp,'input').read_bytes()==b'beta\nalpha\n'
    child = [sys.executable,'-c','import os,signal; os.kill(os.getpid(),signal.SIGTERM)']
    assert run([VLK,'run',*child]).returncode == -signal.SIGTERM
    assert run([VLK,'run','/does/not/exist']).returncode==127
    noexec=Path(tmp,'noexec'); noexec.write_text('test'); assert run([VLK,'run',str(noexec)]).returncode==126

for n in ('0','10','1000'):
    direct=run([FIB,n],env=dict(ENV,VLK_MODE='reference'))
    assert direct.returncode==0 and not direct.stderr
    for mode in ('auto','ground'):
        assert signature(run([VLK,'run',FIB,n],env=dict(ENV,VLK_MODE=mode)))==signature(direct)
assert signature(run([VLK,FIB,'1000000000000']))==(0,b'1115770309 906757858\n',b'')
assert signature(run([FIB,'1000000000000']))==(0,b'1115770309 906757858\n',b'')
assert signature(run([VLK,'shell','-c',f'"{FIB}" 10 | cut -d " " -f 1']))==(0,b'6765\n',b'')
assert run([FIB,'-1']).returncode==2
assert run([FIB,'1000000000000'],env=dict(ENV,VLK_BUDGET='0')).returncode==1
print('Hosted commands: argv, binary streams, environment, cwd, shell pipes, exit/signal parity, executable transparency and budget rejection')
