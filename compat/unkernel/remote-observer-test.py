"""Separate authenticated interpreter processes and detached JS witness verification."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import random
import select
import signal
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from ground_history import GroundHistory, PAGE_SIZE, ZERO
from remote_observer import ObserverHost, context, observe, request, serve_one, check_response

ROOT = Path(__file__).resolve().parents[2]
native = os.environ.get('VLK_NATIVE_ECPU') == '1'
spec = importlib.util.spec_from_file_location('cert_fixture', ROOT / 'tests/observation.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def server(d, mode):
    policy = json.loads((d / 'policy.json').read_text())
    h = GroundHistory(d / (mode + '.sqlite'))
    try:
        host = ObserverHost(h, policy['receipt'], policy['coordinates'])
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen(); listener.settimeout(10)
            print(listener.getsockname()[1], flush=True)
            for _ in range(1 if mode == 'first' else 70):
                try:
                    serve_one(listener, context(d, 'worker', True), host, native=native,
                              before_reply=(lambda: os.kill(os.getpid(), signal.SIGKILL)) if mode == 'first' else None)
                except Exception:
                    # Refusals close their connection without revealing any page.
                    pass
    finally:
        h.close()


def main():
    with TemporaryDirectory() as tmp:
        d = Path(tmp); fixture.certs(d)
        h = GroundHistory(d / 'first.sqlite', pages=16384)
        rng = random.Random(738); basis = rng.randbytes(PAGE_SIZE)
        coords = [i*257 for i in range(32)]
        values = {i: bytes(x ^ (i % 256) for x in basis) for i in coords}
        r = h.commit('main', h.head(), values); receipt = h.receipt(r)
        h.commit('main', r, {0: b'X'*PAGE_SIZE})
        with sqlite3.connect(d / 'replacement.sqlite') as target:
            h.db.backup(target)
        h.close()
        allowed = coords + [16383]
        (d/'policy.json').write_text(json.dumps({'receipt':receipt,'coordinates':allowed}))
        def launch(mode):
            p = subprocess.Popen([sys.executable, __file__, 'server', str(d), mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert select.select([p.stdout], [], [], 10)[0], 'server did not start'
            line = p.stdout.readline(); assert line, p.stderr.read()
            return p, ('127.0.0.1', int(line))
        q = request(receipt, 0)
        p, address = launch('first')
        try:
            try: observe(address, context(d, 'observer'), q, native=native); raise AssertionError('dead host replied')
            except (OSError, EOFError, RuntimeError, ValueError): pass
            assert p.wait(timeout=10) == -signal.SIGKILL
        finally:
            if p.poll() is None: p.kill(); p.wait()
        # The second process has a separately retained copy; no source DB required.
        (d/'first.sqlite').unlink()
        p, address = launch('replacement')
        try:
            w = observe(address, context(d, 'observer'), q, native=native)
            batch = [{'witness':w,'receipt':receipt,'coordinate':0,'expected':values[0].hex()}]
            for i in range(63):
                coord = allowed[i % len(allowed)]; query = request(receipt, coord)
                w = observe(address, context(d, 'observer'), query, native=native)
                batch.append({'witness':w,'receipt':receipt,'coordinate':coord,'expected':values.get(coord,ZERO).hex()})
            # Authenticated but unauthorized peer, no certificate, wrong host, outside coordinate,
            # wrong revision and forged root all refuse without an observation.
            wrong = copy.deepcopy(receipt); wrong['revision'] += 1
            forged = copy.deepcopy(receipt); forged['root'] = 'f'*64
            invalid = [('intruder',q,'worker'),(None,q,'worker'),('observer',q,'wrong'),('observer',request(receipt,1),'worker'),('observer',request(wrong,0),'worker'),('observer',request(forged,0),'worker')]
            for peer, query, hostname in invalid:
                try: observe(address,context(d,peer),query,hostname=hostname,native=native); raise AssertionError('unadmitted observation')
                except (OSError,EOFError,RuntimeError,ValueError): pass
            try: check_response(q, {'nonce':'0'*32,'witness':w}); raise AssertionError('mismatched nonce')
            except ValueError: pass
        finally:
            if p.poll() is None: p.terminate(); p.wait(timeout=10)
        subprocess.run(['node',str(Path(__file__).with_name('remote-verify.mjs'))],input=json.dumps(batch),text=True,check=True,timeout=20)
        print(('native E-CPU transport' if native else 'VL-K TLS framing')+': receiver SIGKILL before reply, replacement database, 64 independently verified observations, 6 admission refusals, nonce refusal passed')


if __name__ == '__main__':
    if len(sys.argv)>1: server(Path(sys.argv[2]),sys.argv[3])
    else: main()
