"""Compile ordinary C to real RV32 ELF and compare native execution and traps."""
import os, random, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from process import Supervisor, PIPE
rng=random.Random(4321)
with tempfile.TemporaryDirectory() as d, Supervisor() as sup:
    d=Path(d)
    def run(args,data=None):
        h=sup.spawn([str(ROOT/'dist/vlk'),*map(str,args)],stdin=PIPE,stdout=PIPE,stderr=PIPE)
        out,err=sup.communicate(h,data,timeout=20);status=sup.wait(h);sup.release(h);return status,out,err
    if "--negative" not in sys.argv:
        for name in ('demo','filter'):
            p=subprocess.run([os.getenv('CC','cc'),'-O2',str(ROOT/'examples/rv32'/f'{name}.c'),'-o',str(d/name)],capture_output=True);assert p.returncode==0,p.stderr
        for i in range(40):
            argv=[str(rng.getrandbits(32)) for _ in range(i%7)]
            assert run(['elf',ROOT/'dist/demo.rv32',*argv])==run(['run',d/'demo',*argv])
        data=rng.randbytes(1024*1024)
        ref=run(['run',d/'filter','Q'],data);assert ref==(0,bytes(v^81 for v in data),b'')
        assert run(['elf',ROOT/'dist/filter.rv32','Q'],data)==ref
        assert run(['elf',ROOT/'dist/abi.rv32'])==(23,b'',b'')
        print('40 compiled C workloads, 1 MiB binary filter, real syscall and RV32M edge cases')
    raw=(ROOT/'dist/demo.rv32').read_bytes();off=struct.unpack_from('<I',raw,28)[0]
    variants=[raw[:51],raw[:16]+b'\x03'+raw[17:],raw[:18]+b'\x03'+raw[19:],raw[:36]+b'\x01'+raw[37:]]
    for field,value in [(off+24,7),(off+16,0xffffffff),(off+8,0xfffffffc),(off+32+8,0x10000)]:
        bad=bytearray(raw);struct.pack_into('<I',bad,field,value);variants.append(bytes(bad))
    for i,code in enumerate(variants):
        p=d/f'bad{i}';p.write_bytes(code);status,out,err=run(['elf',p]);assert status==125 and not out and b'invalid static' in err,(i,status,out,err)
    # Replace entry with invalid instruction, load from unmapped address, store to RX, jump to non-X.
    for i,word in enumerate([0xffffffff,0x00002283,0x00000297,0x00028023,0x00000067]):
        if i==2:continue
        bad=bytearray(raw);start=struct.unpack_from('<I',raw,off+4)[0]
        if i==3:struct.pack_into('<II',bad,start,0x00000297,word)
        else:struct.pack_into('<I',bad,start,word)
        p=d/f'trap{i}';p.write_bytes(bad);status,out,err=run(['elf',p]);assert status==125 and not out and b'trap' in err,(i,status,out,err)
    print('8 malformed ELF files and 4 illegal-instruction/access traps rejected')
# Static Multiboot artifact properties. Runtime smoke is separate QEMU target.
boot=(ROOT/'dist/vlk-boot.elf').read_bytes();pos=boot[:8192].find(struct.pack('<I',0x1badb002));assert pos>=0 and pos%4==0
assert sum(struct.unpack_from('<III',boot,pos))%(2**32)==0
assert struct.unpack_from('<H',boot,18)[0]==3 and struct.unpack_from('<H',boot,16)[0]==2
assert raw in boot
print('Multiboot header, static i386 ELF, exact embedded application validated;',len(boot),'bytes')
