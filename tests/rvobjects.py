import os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    harness=Path(d)/'rvobjects'
    subprocess.run([os.getenv('CC','cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(ROOT/'tests/rvobjects.c'),str(ROOT/'src/rvobjects.c'),'-o',str(harness)],check=True)
    subprocess.run([str(ROOT/'dist/vlk'),'run',str(harness)],check=True,timeout=20)
