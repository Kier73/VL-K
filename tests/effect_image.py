import importlib.util, json, socket, ssl, sqlite3, sys, tempfile, select, os, signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from application import Applications,Sink
from authority import Conflict
from guest_image import pack,unpack
from effect_transport import RemoteSink,accept_one
from process import Supervisor,PIPE
PROGRAM=json.loads((ROOT/'examples/guest-file-xor.json').read_text())['program']
# Reuse existing certificate fixture, not its protocol implementation.
spec=importlib.util.spec_from_file_location('test_certs',ROOT/'tests/observation.py');certs=importlib.util.module_from_spec(spec);spec.loader.exec_module(certs)

def server(d,crash):
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.verify_mode=ssl.CERT_REQUIRED
    ctx.load_verify_locations(d/'ca.crt');ctx.load_cert_chain(d/'worker.crt',d/'worker.key')
    sink=Sink(d/'sink.db')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(15);print(listener.getsockname()[1],sink.identity,flush=True)
        for _ in range(3 if crash else 2):
            raw,_=listener.accept()
            with raw:
                try:accept_one(raw,ctx,'observer',sink,after_commit=(lambda:os.kill(os.getpid(),signal.SIGKILL)) if crash else None)
                except (OSError,EOFError,ValueError,Conflict):pass

if len(sys.argv)>1:
    server(Path(sys.argv[1]),sys.argv[2]=='crash');sys.exit(0)
raw=pack(PROGRAM);assert unpack(raw)==tuple(map(tuple,PROGRAM))
for bad in (raw[:-1],raw+b'!',raw[:15]+bytes([raw[15]^1])+raw[16:]):
    try:unpack(bad);raise AssertionError('bad image accepted')
    except ValueError:pass
with tempfile.TemporaryDirectory() as d,Supervisor() as s:
    d=Path(d);image=d/'file.vka';inp=d/'input.bin';data=bytes(range(256))*64;inp.write_bytes(data)
    h=s.spawn([str(ROOT/'dist/vlk'),'pack',str(ROOT/'examples/guest-file-xor.json'),str(image)],stdout=PIPE,stderr=PIPE)
    out,err=s.communicate(h,timeout=10);assert s.wait(h)==0 and not err and image.read_bytes()==raw;s.release(h)
    # Actual packaged application through the native launcher.
    h=s.spawn([str(ROOT/'dist/vlk'),'app',str(image),str(inp),str(d/'cli.db'),str(d/'cli-sink.db'),'image'],stdout=PIPE,stderr=PIPE)
    out,err=s.communicate(h,timeout=10);assert s.wait(h)==0 and not err;s.release(h)
    assert Sink(d/'cli-sink.db').read('image')==bytes(v^255 for v in data)
    a=Applications(d/'authority.db');a.register('job','owner',PROGRAM,data);receipt=a.run_job('job','owner',1)
    certs.certs(d)
    def launch(mode):
        h=s.spawn([str(ROOT/'dist/vlk'),'run',sys.executable,__file__,str(d),mode],stdout=PIPE,stderr=PIPE);p=s._get(h)
        assert select.select([p.stdout],[],[],15)[0];port,identity=p.stdout.readline().decode().split();return h,('127.0.0.1',int(port)),identity
    h,address,identity=launch('crash')
    def remote(name,identity=identity):
        ctx=ssl.create_default_context(cafile=str(d/'ca.crt'));ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(d/(name+'.crt'),d/(name+'.key'));return RemoteSink(identity,address,ctx,'worker')
    # Wrong SAN and wrong destination rejected before effect insertion.
    for peer in (remote('intruder'),remote('observer','0'*32)):
        try:peer.accept(receipt,bytes(v^255 for v in data));raise AssertionError('invalid remote sink accepted')
        except (OSError,EOFError,ValueError):pass
    try:a.deliver('job',remote('observer'));raise AssertionError('acknowledged dead receiver')
    except (OSError,EOFError):pass
    assert s.wait(h,timeout=10)==-9;s.release(h)
    with sqlite3.connect(d/'authority.db') as c:assert c.execute('SELECT acknowledged FROM app_outbox').fetchone()==(0,)
    assert Sink(d/'sink.db').read('job')==bytes(v^255 for v in data)
    h,address,new_identity=launch('retry');assert identity==new_identity
    assert a.deliver('job',remote('observer'))==receipt
    assert a.deliver('job',remote('observer'))==receipt
    out,err=s.communicate(h,timeout=15);assert s.wait(h)==0 and not err;s.release(h)
    local=Sink(d/'sink.db');assert local.identity==identity and local.read('job')==bytes(v^255 for v in data)
    with sqlite3.connect(d/'sink.db') as c:assert c.execute('SELECT count(*) FROM output').fetchone()==(1,)
    other=Sink(d/'other.db')
    try:a.deliver('job',other);raise AssertionError('destination changed')
    except Conflict:pass
    with sqlite3.connect(d/'other.db') as c:assert c.execute('SELECT count(*) FROM output').fetchone()==(0,)
    # An old outbox row with no destination metadata cannot silently acquire a new sink.
    with a.transaction() as c:c.execute('DELETE FROM app_destination WHERE id=?',('job',))
    try:a.deliver('job',other);raise AssertionError('legacy output rebound')
    except Conflict:pass
    print('portable image',len(raw),'bytes; 3 malformed images rejected; native launcher output exact; mTLS remote delivery, receiver SIGKILL after insert before reply, 2 refusals, 2 retries, duplicate insertion avoided; sink rebinding and legacy ambiguity rejected')
