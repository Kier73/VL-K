import os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    harness=Path(d)/'control';cc=os.getenv('CC','cc')
    subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),*[str(ROOT/p) for p in ('tests/guest_control.c','src/rvproc.c','src/rv32.c','src/rvfs.c')],'-o',str(harness)],check=True)
    subprocess.run([str(ROOT/'dist/vlk'),'run',str(harness),str(ROOT/'dist/control.rv32'),str(ROOT/'dist/worker.rv32')],check=True,timeout=20)
# Exercise the real hosted command surface, not just the native scheduler harness.
cmd=[str(ROOT/'dist/vlk'),'session',str(ROOT/'dist/shell.rv32'),f'demo={ROOT}/dist/demo.rv32',f'filter={ROOT}/dist/filter.rv32']
p=subprocess.run(cmd,input=b'run demo kernel\nrun missing\nsend abc | filter Q\nquit\n',capture_output=True,timeout=20)
assert (p.returncode,p.stdout,p.stderr)==(0,b'guest> demo 54c69d41\nok\nguest> failed\nguest> 032ok\nguest> ',b''),p
print('actual guest shell launched two admitted executables and rejected an unknown name')
