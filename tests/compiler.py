"""Guest code generation, independent expression oracle, ELF inspection and execution."""
from pathlib import Path
import random, struct, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'dist'; rng=random.Random(31921); mask=2**32-1

def session(backend, commands):
    p=subprocess.run([str(D/backend),str(D/'shell.rv32'),f'cc={D}/compiler.rv32'],input=commands,capture_output=True,timeout=20)
    assert p.returncode==0 and not p.stderr,p
    return p.stdout

def expression(depth):
    if depth==0 or rng.random()<.32:
        if rng.random()<.5:return ['in'],1
        return [str(rng.randrange(2**32))],0
    l,a=expression(depth-1);r,b=expression(depth-1)
    return l+r+[rng.choice(['add','sub','mul','xor','shr','div'])],a+b

def evaluate(tokens,data):
    it=iter(data);s=[];out=bytearray()
    for t in tokens:
        if t=='in':s.append(next(it))
        elif t=='out':assert len(s)==1;out.append(s.pop()&255)
        elif t in ('add','sub','mul','xor','shr','div'):
            b=s.pop();a=s.pop();s.append({'add':lambda:a+b,'sub':lambda:a-b,'mul':lambda:a*b,'xor':lambda:a^b,'shr':lambda:a>>(b&31),'div':lambda:a//b if b else mask}[t]()&mask)
        else:s.append(int(t))
    assert not s
    return bytes(out)

cases=[(['4294967295','2','add','out'],b''),(['in','in','sub','out'],b'AZ'),(['in','in','mul','out','in','out'],b'ABC'),(['0','1','sub','out'],b''),(['in','0','mul','out','in','out'],b'AB'),(['4294967295','2','add','24','shr','out'],b''),(['4294967295','in','div','24','shr','out'],b'A'),(['2147483648','in','shr','out'],b'Z'),(['in','0','div','out'],b'A')]
while len(cases)<40:
    t,n=expression(3);t+=['out'];src=','.join(t)
    if len(src)>96:continue
    cases.append((t,bytes(rng.randrange(65,91) for _ in range(n))))
for backend in ('vlk-session','vlk-session-objects'):
    for base in range(0,len(cases),8):
        cmds=b'';expected=b''
        for i,(t,data) in enumerate(cases[base:base+8]):
            name=f'p{i}'.encode();src=','.join(t).encode();cmds+=b'send '+src+b' | cc '+name+b'\n'
            cmds+=(b'send '+data+b' | ./'+name if data else b'run ./'+name)+b'\n';expected+=b'guest> ok\nguest> '+evaluate(t,data)+b'ok\n'
        assert session(backend,cmds+b'quit\n')==expected+b'guest> '
    invalid=['1,add,out','1,2,out','1','4294967296,out','in,,out','1,out,','out','1,wat,out','1,2,add,out,5']
    commands=b''.join(b'send '+s.encode()+b' | cc bad\n' for s in invalid)+b'run ./bad\nsend 65,out | cc bad\nsend 66,out | cc bad\nrun ./bad\nquit\n'
    expected=b'guest> failed\n'*(len(invalid)+1)+b'guest> ok\nguest> failed\nguest> Aok\nguest> '
    assert session(backend,commands)==expected
    # A runtime read cannot be folded away even when multiplied by zero.
    assert session(backend,b'send in,in,0,mul,add,out | cc r\nsend A | ./r\nquit\n')==b'guest> ok\nguest> failed\nguest> '
    print(f'{backend}: 40 generated programs, 9 invalid sources, no failed-source files, duplicate protection and EOF effect preservation')

# Capture the actual guest-generated ELF, not a host assembler's output.
def elf(src):
    out=session('vlk-session-objects',b'send '+src+b' | cc -\nquit\n');assert out.startswith(b'guest> \x7fELF') and out.endswith(b'ok\nguest> ')
    image=out[7:-10];h=struct.unpack_from('<16sHHIIIIIHHHHHH',image);assert h[1:5]==(2,243,1,65536) and h[5]==52 and h[8:11]==(52,32,1)
    segment=struct.unpack_from('<8I',image,52);assert segment[:4]==(1,84,65536,65536) and segment[4]==segment[5]==len(image)-84 and segment[6:]==(5,4)
    return image
fold=elf(b'12,3,mul,29,add,out');lit=elf(b'65,out');dynamic=elf(b'in,3,mul,29,add,out')
assert fold==lit and len(dynamic)>len(fold)
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/'generated.elf';p.write_bytes(dynamic)
    result=subprocess.run([str(D/'vlk-elf'),str(p)],input=b'\x0c',capture_output=True,timeout=10);assert (result.returncode,result.stdout,result.stderr)==(0,b'A',b'')
print(f'guest-generated ELF: folded {len(fold)} B, dynamic {len(dynamic)} B; folded bytes identical to literal; separate execution passed')
