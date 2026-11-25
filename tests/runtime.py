"""Actual compiled guest startup/memory probe; separate native loader boundary test."""
import os, subprocess, tempfile, sys, struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from process import Supervisor,PIPE
with tempfile.TemporaryDirectory() as d,Supervisor() as sup:
    def run(*args):
        h=sup.spawn([str(ROOT/'dist/vlk'),*map(str,args)],stdout=PIPE,stderr=PIPE)
        out,err=sup.communicate(h,timeout=20);status=sup.wait(h);sup.release(h);return status,out,err
    image=ROOT/'dist/runtime.rv32'
    for _ in range(16):assert run('elf','--env','MODE=vlk',image,'kernel')==(0,b'runtime ABI passed\n',b'')
    assert run('elf',image,'kernel')[0]==11
    assert run('elf','--env','MODE=wrong',image,'kernel')[0]==11
    assert run('elf','--env','invalid',image,'kernel')[0]==2
    tool=Path(d)/'runtime-boundary'
    assert run('run',os.getenv('CC','cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),'-I'+str(ROOT/'boot'),ROOT/'tests/runtime.c',ROOT/'src/rv32.c',ROOT/'src/rvfs.c','-o',tool)[0]==0
    status,out,err=run('run',tool,image);assert status==0 and not err;print(out.decode(),end='')
    boot=(ROOT/'dist/vlk-boot.elf').read_bytes();raw=image.read_bytes();assert raw not in boot
    pos=boot[:8192].find(struct.pack('<I',0x1badb002));assert pos>=0 and struct.unpack_from('<I',boot,pos+4)[0]==2
    assert sum(struct.unpack_from('<III',boot,pos))%2**32==0
    print('16 fresh compiled runtime executions; 3 invalid environment requests; external ELF not embedded in boot image')
