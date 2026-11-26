import os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    harness=Path(d)/'cow';cc=os.getenv('CC','cc')
    subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),*[str(ROOT/p) for p in ('tests/cow.c','src/rvproc.c','src/rv32.c','src/rvfs.c')],'-o',str(harness)],check=True)
    subprocess.run([str(ROOT/'dist/vlk'),'run',str(harness),str(ROOT/'dist/cow.rv32')],check=True,timeout=20)
