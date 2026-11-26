"""Compare compiled workloads under the existing and experimental page backends."""
import os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
cc=os.getenv('CC','cc')
with tempfile.TemporaryDirectory() as d:
    d=Path(d)
    def build(name,test,flags):
        target=d/name
        sources=[test,'src/rvproc.c','src/rv32.c','src/rvfs.c']
        if '-DRV_OBJECT_BACKEND' in flags:sources.append('src/rvobjects.c')
        subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),*flags,*[str(ROOT/p) for p in sources],'-o',str(target)],check=True)
        return target
    flags=['-DRV_OBJECT_BACKEND','-DRO_OBJECTS=1024']
    def run(binary,*args):
        return subprocess.run([str(ROOT/'dist/vlk'),'run',str(binary),*map(str,args)],capture_output=True,check=True,timeout=30)
    args=[ROOT/'dist'/p for p in ('cow.rv32','demo.rv32','runtime.rv32')]
    reference=run(build('flat','tests/object_runtime.c',['-DRP_SLOTS=4']),*args)
    pooled=run(build('pooled','tests/object_runtime.c',[*flags,'-DRP_SLOTS=4']),*args)
    assert reference.stdout==pooled.stdout,(reference,pooled)
    print(pooled.stdout.decode(),end='');print(pooled.stderr.decode(),end='')
    control=run(build('control','tests/guest_control.c',flags),ROOT/'dist/control.rv32',ROOT/'dist/worker.rv32')
    print(control.stdout.decode(),end='')
    cmd=[str(ROOT/'dist/vlk-session-objects'),str(ROOT/'dist/shell.rv32'),f'demo={ROOT}/dist/demo.rv32',f'filter={ROOT}/dist/filter.rv32']
    shell=subprocess.run(cmd,input=b'run demo kernel\nrun missing\nsend abc | filter Q\nquit\n',capture_output=True,check=True,timeout=20)
    assert shell.stdout==b'guest> demo 54c69d41\nok\nguest> failed\nguest> 032ok\nguest> ' and not shell.stderr
    print('pooled guest shell matched expected transcript')
