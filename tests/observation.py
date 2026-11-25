"""Real mutually authenticated loopback TCP, separate receiver, bounded pure jobs."""
import copy
import json
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from observation import ObservationHost, request, verify
from loop_receipt import digest, canonical
from process import Supervisor, PIPE
PROGRAM=json.loads((ROOT/'examples/guest-debug.json').read_text())['program']
CUT=32212254723
END=32212254728
LIMIT=16384


def exact(sock,n):
    data=bytearray()
    while len(data)<n:
        b=sock.recv(n-len(data))
        if not b: raise EOFError('truncated frame')
        data.extend(b)
    return bytes(data)


def receive(sock):
    n=struct.unpack('!I',exact(sock,4))[0]
    if not 0<n<=LIMIT: raise ValueError('frame size')
    return json.loads(exact(sock,n))


def send(sock,value):
    b=canonical(value).encode('ascii')
    assert 0<len(b)<=LIMIT
    sock.sendall(struct.pack('!I',len(b))+b)


def server(directory):
    d=Path(directory)
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(d/'ca.crt');ctx.load_cert_chain(d/'worker.crt',d/'worker.key');ctx.verify_mode=ssl.CERT_REQUIRED
    host=ObservationHost([PROGRAM],max_tick=END)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(10)
        print(listener.getsockname()[1],flush=True)
        for _ in range(3):
            raw,_=listener.accept();raw.settimeout(5)
            with raw:
                try:
                    with ctx.wrap_socket(raw,server_side=True) as conn:
                        if ('DNS','observer') not in conn.getpeercert().get('subjectAltName',()): raise ValueError('peer not authorized')
                        for _ in range(5):
                            try: q=receive(conn)
                            except EOFError: break
                            try: send(conn,{'ok':host.observe(q)})
                            except (ValueError,RuntimeError): send(conn,{'error':'refused'})
                except (ssl.SSLError,ValueError,EOFError): pass


def certs(d):
    def run(*args): subprocess.run(['openssl',*args],cwd=d,check=True,capture_output=True,timeout=10)
    run('req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.crt','-days','1','-subj','/CN=VLK-test-CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign')
    for name in ('worker','observer','intruder'):
        run('req','-newkey','rsa:2048','-nodes','-keyout',name+'.key','-out',name+'.csr','-subj','/CN='+name)
        Path(d,name+'.ext').write_text('subjectAltName=DNS:'+name+'\n')
        run('x509','-req','-in',name+'.csr','-CA','ca.crt','-CAkey','ca.key','-CAcreateserial','-out',name+'.crt','-days','1','-extfile',name+'.ext')


def client(d,port,name):
    ctx=ssl.create_default_context(cafile=str(Path(d,'ca.crt')))
    if name: ctx.load_cert_chain(Path(d,name+'.crt'),Path(d,name+'.key'))
    raw=socket.create_connection(('127.0.0.1',port),timeout=5)
    try: return ctx.wrap_socket(raw,server_hostname='worker')
    except BaseException: raw.close();raise


def main():
    q=request(PROGRAM,CUT);host=ObservationHost([PROGRAM],max_tick=END)
    local=host.observe(q);assert verify(local,q,PROGRAM)
    # Independent arithmetic, not another call to the same optimizer.
    x=2*(pow(3,2**31-1,2**32)-1)&0xffffffff
    state=local['body']['checkpoint']['body']['state']
    assert state=={'tick':str(CUT),'pc':13,'registers':[3*(x+1)&0xffffffff,1,1,1,1,1,0xffffffff,3],'halted':False,'status':None}
    forged=copy.deepcopy(local);cp=forged['body']['checkpoint'];cp['body']['state']['registers'][0]^=1;cp['sha256']=digest(cp['body']);forged['sha256']=digest(forged['body'])
    assert not verify(forged,q,PROGRAM)
    with tempfile.TemporaryDirectory() as d:
        certs(d)
        p=subprocess.Popen([sys.executable,__file__,'server',d],stdout=PIPE,stderr=PIPE,text=True)
        try:
            import select
            assert select.select([p.stdout],[],[],10)[0]
            port=int(p.stdout.readline())
            for name in (None,'intruder'):
                try:
                    with client(d,port,name) as conn: send(conn,q);receive(conn)
                except (ssl.SSLError,EOFError,ConnectionError): pass
                else: raise AssertionError('unauthorized peer admitted')
            with client(d,port,'observer') as conn:
                send(conn,q);remote=receive(conn)['ok'];assert remote==local and verify(remote,q,PROGRAM)
                for bad in (dict(q,program_sha256='0'*64),dict(q,tick=str(END+1)),dict(q,tick='01'),dict(q,version=True)):
                    send(conn,bad);assert receive(conn)=={'error':'refused'}
            assert p.wait(timeout=10)==0,p.stderr.read()
        finally:
            if p.poll() is None:p.kill()
            p.communicate(timeout=10)
    # Receiver is gone. Start a different VL-K process using the transported checkpoint.
    with tempfile.TemporaryDirectory() as d:
        path=Path(d,'checkpoint.json');path.write_text(canonical(remote['body']['checkpoint']))
        with Supervisor() as s:
            h=s.spawn([str(ROOT/'dist/vlk'),'debug',str(ROOT/'examples/guest-debug.json'),'--restore',str(path)],stdin=PIPE,stdout=PIPE,stderr=PIPE)
            out,err=s.communicate(h,b'step 5\nquit\n',timeout=10);assert s.wait(h)==0 and not err
            final=json.loads(out);assert final['tick']==str(END) and final['halted'] and final['registers'][0]==0
    print('mTLS loopback: two rejected peers, four rejected requests, rehashed forgery rejected, remote observation and fresh-process continuation; request bytes',len(canonical(q)),'result bytes',len(canonical(remote)))

if __name__=='__main__':
    if len(sys.argv)>1: server(sys.argv[2])
    else: main()
