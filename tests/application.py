import json, os, random, select, sqlite3, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from application import Applications, Sink, execute, LIMIT
from authority import Conflict
from process import Supervisor, PIPE
PROGRAM=json.loads((ROOT/'examples/guest-file-xor.json').read_text())['program']

if len(sys.argv)>1:
    a=Applications(sys.argv[1]);s=Sink(sys.argv[2])
    def stop(): print('sink committed',flush=True);time.sleep(60)
    if len(sys.argv)==4 and sys.argv[3]=='retry':
        print(json.dumps(a.deliver('job',s),sort_keys=True));sys.exit(0)
    a.deliver('job',s,after_sink=stop);sys.exit(0)

rng=random.Random(911);data=rng.randbytes(16384);expected=bytes(v^255 for v in data)
with tempfile.TemporaryDirectory() as d, Supervisor(8) as sup:
    d=Path(d);db=d/'authority.db';sd=d/'sink.db';a=Applications(db);s=Sink(sd)
    a.register('job','origin',PROGRAM,data)
    try:a.deliver('job',s);raise AssertionError('uncommitted delivery')
    except Conflict:pass
    a.transfer_job('job','origin',1,'worker')
    try:a.run_job('job','origin',1);raise AssertionError('stale owner')
    except Conflict:pass
    receipt=a.run_job('job','worker',2);assert a.run_job('job','worker',2)==receipt
    h=sup.spawn([str(ROOT/'dist/vlk'),'run',sys.executable,__file__,str(db),str(sd)],stdout=PIPE,stderr=PIPE)
    p=sup._get(h);assert select.select([p.stdout],[],[],15)[0] and p.stdout.readline()==b'sink committed\n'
    sup.kill(h);assert sup.wait(h,timeout=10)==-9;sup.release(h)
    assert s.read('job')==expected
    with sqlite3.connect(db) as c:assert c.execute('SELECT acknowledged FROM app_outbox').fetchone()==(0,)
    a.transfer_job('job','worker',2,'replacement')
    hs=[sup.spawn([str(ROOT/'dist/vlk'),'run',sys.executable,__file__,str(db),str(sd),'retry'],stdout=PIPE,stderr=PIPE) for _ in range(8)]
    for h in hs:
        out,err=sup.communicate(h,timeout=20);assert sup.wait(h)==0 and not err and json.loads(out)==receipt;sup.release(h)
    for _ in range(4):assert a.deliver('job',s)==receipt
    with sqlite3.connect(db) as c:assert c.execute('SELECT acknowledged FROM app_outbox').fetchone()==(1,)
    with sqlite3.connect(sd) as c:assert c.execute('SELECT count(*) FROM output').fetchone()==(1,) and c.execute('PRAGMA integrity_check').fetchone()==('ok',)
    # Actual CLI application consumes a file, with no path capability in the guest.
    inp=d/'input.bin';inp.write_bytes(data)
    for _ in range(2):
        h=sup.spawn([str(ROOT/'dist/vlk'),'app',str(ROOT/'examples/guest-file-xor.json'),str(inp),str(db),str(sd),'cli'],stdout=PIPE,stderr=PIPE)
        out,err=sup.communicate(h,timeout=20);assert sup.wait(h)==0 and not err and s.read('cli')==expected;sup.release(h)
    with sqlite3.connect(sd) as c:assert c.execute('SELECT count(*) FROM output').fetchone()==(2,)
    try:a.register('cli','local',PROGRAM,b'changed');raise AssertionError('changed input replay')
    except Conflict:pass
    # Incorrect descriptor rights, failed app, no output publication.
    bad=[['set',1,3],['writefd',1,0],['halt',0]];a.register('bad','worker',bad,b'')
    try:a.run_job('bad','worker',1);raise AssertionError('read-only descriptor writable')
    except PermissionError:pass
    try:a.deliver('bad',s);raise AssertionError('failed job delivered')
    except Conflict:pass
    try:execute([['set',1,1],['writefd',1,0],['jmp',1]],b'');raise AssertionError('unbounded output')
    except RuntimeError:pass
    try:s.accept(dict(receipt,steps=0),expected);raise AssertionError('conflicting sink receipt')
    except Conflict:pass
    print('file application:',len(data),'bytes,',receipt['steps'],'guest instructions; SIGKILL after sink commit, 12 duplicate deliveries, one sink row, CLI output exact; capability and output limit rejections')
