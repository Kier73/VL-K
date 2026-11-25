"""Boot smoke test on a PC emulator, not a hosted guest or a mocked UART."""
import os, select, shutil, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
qemu=shutil.which('qemu-system-i386') or shutil.which('qemu-system-x86_64')
if not qemu: raise SystemExit('QEMU required for boot runtime validation')
p=subprocess.Popen([qemu,'-machine','pc','-m','32M','-display','none','-monitor','none','-serial','stdio','-no-reboot','-no-shutdown','-kernel',str(ROOT/'dist/vlk-boot.elf'),'-initrd',str(ROOT/'dist/runtime.rv32')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
transcript=bytearray()
def expect(marker):
    deadline=time.monotonic()+20
    while marker not in transcript:
        remaining=deadline-time.monotonic()
        if remaining<=0 or not select.select([p.stdout],[],[],remaining)[0]:raise AssertionError(bytes(transcript))
        chunk=os.read(p.stdout.fileno(),4096)
        if not chunk:raise AssertionError(bytes(transcript))
        transcript.extend(chunk)
def command(line,marker):
    transcript.clear();p.stdin.write(line+b'\n');p.stdin.flush();expect(marker)
try:
    expect(b'vlk> ')
    assert b'VL-K bare metal' in transcript and b'external module available' in transcript and b'demo 54c69d41\n' in transcript and b'guest exited 0' in transcript,bytes(transcript)
    command(b'help',b'help run file external halt\r\n');expect(b'vlk> ')
    command(b'run',b'guest exited 0');expect(b'vlk> ');assert b'demo 54c69d41\n' in transcript
    command(b'file',b'count 01\n');expect(b'vlk> ')
    command(b'file',b'count 02\n');expect(b'vlk> ')
    command(b'external',b'external exited 0');expect(b'vlk> ');assert b'runtime ABI passed\n' in transcript
    command(b'halt',b'halted\r\n')
    print('QEMU Multiboot entry, real serial shell, repeated RV32 ELF execution, external ELF module, halt command passed')
finally:
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
