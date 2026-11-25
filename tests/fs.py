"""Compiled RV32 file operations against native POSIX and an independent volume parser."""
import fcntl, os, random, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from process import Supervisor, PIPE

def parse(raw):
    assert raw[:8]==b'VLKFS1\0\0';i=8;out={}
    while i<len(raw):
        n,size=struct.unpack_from('<BI',raw,i);i+=5
        name=raw[i:i+n].decode('ascii');i+=n;assert name not in out and i+size<=len(raw)
        out[name]=raw[i:i+size];i+=size
    assert i==len(raw);return out

rng=random.Random(31415)
with tempfile.TemporaryDirectory() as tmp,Supervisor() as sup:
    d=Path(tmp);native=d/'file';work=d/'native';work.mkdir();volume=d/'volume'
    subprocess.run([os.getenv('CC','cc'),'-O2',str(ROOT/'examples/rv32/file.c'),'-o',str(native)],check=True)
    def run(cmd,data=b''):
        h=sup.spawn([str(ROOT/'dist/vlk'),*map(str,cmd)],stdin=PIPE,stdout=PIPE,stderr=PIPE,cwd=work)
        out,err=sup.communicate(h,data,timeout=15);status=sup.wait(h);sup.release(h);return status,out,err
    def guest(args,data=b''):return run(['elf','--volume',volume,ROOT/'dist/file.rv32',*args],data)
    def both(args,data=b''):
        a=guest(args,data);b=run(['run',native,*args],data);assert a==b,(args,a[:1],b[:1],a[2],b[2]);return a
    data=rng.randbytes(192*1024);extra=rng.randbytes(4096)
    assert both(['put','source'],data)==(0,b'',b'')
    assert both(['append','source'],extra)==(0,b'',b'')
    assert both(['xor','source','output'])==(0,b'',b'')
    expected=bytes(v^0xa5 for v in data+extra)
    assert both(['get','output'])==(0,expected,b'')
    assert both(['tail','output'])==(0,expected[-16:],b'')
    assert parse(volume.read_bytes())=={'source':data+extra,'output':expected}
    for i in range(1,9):assert both(['count','counter'])==(0,f'count {i:02x}\n'.encode(),b'')
    assert both(['rm','source'])==(0,b'',b'')
    assert both(['get','source'])==(3,b'',b'')
    assert parse(volume.read_bytes())=={'output':expected,'counter':b'\x08'}
    assert both(['probe','sparse'])==(0,b'',b'')
    assert parse(volume.read_bytes())['sparse']==b'\0'*4095+b'QQ'
    assert guest(['quota','quota'])==(0,b'',b'')
    # failed guest job must not publish truncation or partial output
    original=volume.read_bytes();assert guest(['fail','output'],b'changed')[0]==19;assert volume.read_bytes()==original
    assert guest(['put','too-big'],b'x'*(256*1024+1))[0]==5;assert volume.read_bytes()==original
    assert guest(['put','../escape'],b'x')[0]==3;assert not (d/'escape').exists();assert volume.read_bytes()==original
    # independent process may not open a busy volume
    with open(str(volume)+'.lock','rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert guest(['get','output'])[0]==125
    assert volume.read_bytes()==original
    # reject malformed/truncated/duplicate/invalid names and never overwrite
    for raw in (b'',b'wrong!!!',original[:-1],original+original[8:],b'VLKFS1\0\0'+struct.pack('<BI',3,0)+b'a\0b',b'VLKFS1\0\0'+struct.pack('<BI',1,2**32-1)+b'x'):
        volume.write_bytes(raw);assert guest(['get','output'])[0]==125;assert volume.read_bytes()==raw
    volume.write_bytes(original);assert guest(['get','output'])==(0,expected,b'')
    print('16 native/guest command comparisons; independent descriptors, seek gaps, append and descriptor quota; 196 KiB file transform; 8 process restarts; exact persisted contents; failed/oversized/traversal/busy/6 malformed volume cases rejected')
