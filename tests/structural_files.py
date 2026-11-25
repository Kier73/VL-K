"""Run unchanged guest file utility against two persisted representations."""
import os, random, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from process import Supervisor, PIPE

def decode(raw):
    assert raw[:8] in (b'VLKFS1\0\0',b'VLKFS2\0\0');compact=raw[5]==50;pos=8;files={};tags=[]
    while pos<len(raw):
        n,size=struct.unpack_from('<BI',raw,pos);pos+=5;name=raw[pos:pos+n].decode('ascii');pos+=n;assert name not in files
        value=bytearray()
        while len(value)<size:
            k=min(4096,size-len(value));tag=raw[pos] if compact else 255;pos+=int(compact);tags.append(tag)
            if tag==255:part=raw[pos:pos+k];pos+=k
            elif 0<=tag<=16:
                pattern=raw[pos:pos+tag];pos+=tag;assert len(pattern)==tag
                part=((pattern*((k+tag-1)//tag))[:k] if tag else bytes(k))
            else:raise AssertionError('invalid tag')
            assert len(part)==k;value.extend(part)
        files[name]=bytes(value)
    assert pos==len(raw);return files,tags

with tempfile.TemporaryDirectory() as tmp,Supervisor() as sup:
    d=Path(tmp);harness=d/'oracle';volume=d/'volume';cc=os.getenv('CC','cc')
    subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(ROOT/'tests/structural_files.c'),str(ROOT/'src/rvfs.c'),'-o',str(harness)],check=True)
    def run(*args,data=b''):
        h=sup.spawn([str(ROOT/'dist/vlk'),*map(str,args)],stdin=PIPE,stdout=PIPE,stderr=PIPE)
        out,err=sup.communicate(h,data,timeout=20);status=sup.wait(h);sup.release(h);return status,out,err
    status,out,err=run('run',harness);assert status==0 and not err;print(out.decode(),end='')
    def guest(*args,data=b'',compact=True):return run('elf','--compact-volume' if compact else '--volume',volume,ROOT/'dist/file.rv32',*args,data=data)
    pattern=(b'abcdefg'*40000)[:262144];assert guest('put','pattern',data=pattern,compact=False)==(0,b'',b'')
    original=volume.read_bytes();assert decode(original)[0]=={'pattern':pattern}
    assert guest('get','pattern')==(0,pattern,b'');small=volume.read_bytes();assert decode(small)==({'pattern':pattern},[7]*64)
    print('actual guest V1 -> V2:',len(original),'->',len(small),'bytes')
    assert guest('count','pattern')==(0,b'count 62\n',b'');changed=b'b'+pattern[1:];assert decode(volume.read_bytes())[0]=={'pattern':changed};assert decode(volume.read_bytes())[1]==[255]+[7]*63
    assert guest('xor','pattern','output')==(0,b'',b'');expected=bytes(v^0xa5 for v in changed);assert guest('get','output')==(0,expected,b'')
    random_data=random.Random(88).randbytes(65536);assert guest('put','random',data=random_data)==(0,b'',b'');assert guest('get','random')==(0,random_data,b'')
    assert guest('probe','hole')==(0,b'',b'');assert decode(volume.read_bytes())[0]=={'pattern':changed,'output':expected,'random':random_data,'hole':bytes(4095)+b'QQ'}
    assert guest('get','pattern',compact=False)==(0,changed,b'');assert volume.read_bytes()[:8]==b'VLKFS1\0\0'
    assert guest('get','pattern')==(0,changed,b'');before=volume.read_bytes();assert guest('fail','pattern',data=b'bad')[0]==19 and volume.read_bytes()==before
    # Tag, length, truncation, duplicate names: fail without changing source volume.
    prefix=b'VLKFS2\0\0'+struct.pack('<BI',1,4096)+b'x'
    for raw in (prefix+b'\x11',prefix+b'\x07abc',prefix+b'\xffabc',before[:-1],before+before[8:]):
        volume.write_bytes(raw);assert guest('get','pattern')[0]==125 and volume.read_bytes()==raw
    volume.write_bytes(before);assert guest('get','output')==(0,expected,b'')
    print('periodic/dense transition, XOR, random fallback, seek holes, V2 -> V1 -> V2, rollback and 5 malformed V2 cases passed')
