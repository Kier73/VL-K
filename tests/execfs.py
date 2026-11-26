"""Install an actual separately compiled executable using guest syscalls, then exec it."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
image=(ROOT/'dist/demo.rv32').read_bytes()
for backend in ('vlk-session','vlk-session-objects'):
    cmd=[str(ROOT/'dist'/backend),str(ROOT/'dist/execfs.rv32')]
    p=subprocess.run(cmd,input=image,capture_output=True,timeout=20)
    assert (p.returncode,p.stdout,p.stderr)==(0,b'demo 54c69d41\ndemo 54c69d41\nfilesystem executable passed\n',b''),p
    # An existing catalogue entry must not override an explicit filesystem path.
    p=subprocess.run([*cmd,f'tool={ROOT}/dist/filter.rv32'],input=image,capture_output=True,timeout=20)
    # The guest's second (bare-name) execution selects the catalogue, not the FS.
    assert (p.returncode,p.stdout,p.stderr)==(0,b'demo 54c69d41\nfilesystem executable passed\n',b''),p
    print(f'{backend}: installed {len(image)} bytes; filesystem exec, catalogue precedence and permission checks passed')
    # A conventional interactive guest can ingest binary bytes without a host command parser.
    cmd=[str(ROOT/'dist'/backend),str(ROOT/'dist/shell.rv32')]
    header=f'install newapp {len(image)}\n'.encode()
    p=subprocess.run(cmd,input=header+image+b'run ./newapp kernel\nquit\n',capture_output=True,timeout=20)
    assert (p.returncode,p.stdout,p.stderr)==(0,b'guest> ok\nguest> demo 54c69d41\nok\nguest> ',b''),p
    p=subprocess.run(cmd,input=header+image[:100],capture_output=True,timeout=20)
    assert (p.returncode,p.stdout,p.stderr)==(4,b'guest> install failed\n',b''),p
    p=subprocess.run(cmd,input=header+image+header+image,capture_output=True,timeout=20)
    assert (p.returncode,p.stdout,p.stderr)==(4,b'guest> ok\nguest> install failed\n',b''),p
    p=subprocess.run(cmd,input=b'install x 262145\nquit\n',capture_output=True,timeout=20)
    assert (p.returncode,p.stdout,p.stderr)==(0,b'guest> failed\nguest> ',b''),p
    print(f'{backend}: shell binary install and launch, truncated transfer, duplicate and oversized size tests passed')
