import os, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp);native=d/'native';harness=d/'harness';cc=os.getenv('CC','cc')
    subprocess.run([cc,'-O2',str(ROOT/'examples/rv32/descriptor.c'),'-o',str(native)],check=True)
    def run(*cmd):return subprocess.run(cmd,cwd=d,capture_output=True,timeout=10)
    a=run(str(native),'nativefile');b=run(str(ROOT/'dist/vlk'),'elf','--volume',str(d/'vfs'),str(ROOT/'dist/descriptor.rv32'),'guestfile')
    assert (a.returncode,a.stdout,a.stderr)==(b.returncode,b.stdout,b.stderr)==(0,b'descriptor ABI passed\n',b''),(a,b)
    assert (d/'nativefile').read_bytes()==b'abcdE' and (d/'vfs').read_bytes().endswith(b'abcdE')
    subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(ROOT/'tests/descriptors.c'),str(ROOT/'src/rv32.c'),str(ROOT/'src/rvfs.c'),'-o',str(harness)],check=True)
    p=run(str(harness),str(ROOT/'dist/descriptor.rv32'));assert p.returncode==0,p;print(p.stdout.decode(),end='')
    print('native and guest descriptor/statx probe matched; exact persisted bytes')
