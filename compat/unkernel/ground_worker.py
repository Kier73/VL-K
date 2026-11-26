"""One persistent, bounded local pathway to E-CPU-backed coordinate Grounds."""
import base64
import json
import sys
from ground_history import GroundHistory, PAGE_SIZE

LIMIT = 1024 * 1024
FRAME = 2 * LIMIT


def serve(h, branch):
    revision = h.head(branch)
    pending = {}
    size = h.pages * PAGE_SIZE

    def receipt():
        return {**h.receipt(revision), 'branch': branch, 'dirty': bool(pending)}

    def check(off, n):
        if type(off) is not int or type(n) is not int or off < 0 or n < 0 or off % 512 or n % 512 or n > LIMIT or off > size or n > size-off:
            raise ValueError('invalid sector request')

    def page(i):
        return pending[i] if i in pending else h.observe(revision, i)

    def dispatch(q):
        nonlocal revision
        op = q['op']
        if op == 'witness':
            return h.witness(q['revision'], q['coordinate'])
        if op == 'receipt':
            return receipt()
        if op == 'read':
            off, n = q['off'], q['length']; check(off, n)
            out = bytearray()
            while n:
                i, at = divmod(off, PAGE_SIZE); take = min(n, PAGE_SIZE-at)
                out.extend(page(i)[at:at+take]); off += take; n -= take
            return base64.b64encode(out).decode('ascii')
        if op == 'write':
            off = q['off']; raw = base64.b64decode(q['data'], validate=True); check(off, len(raw))
            updates = {}; pos = 0
            while pos < len(raw):
                i, at = divmod(off+pos, PAGE_SIZE); take = min(len(raw)-pos, PAGE_SIZE-at)
                b = bytearray(page(i)); b[at:at+take] = raw[pos:pos+take]
                updates[i] = bytes(b); pos += take
            pending.update(updates)
            return receipt()
        if op == 'flush':
            revision = h.commit(branch, revision, pending)
            pending.clear()
            return receipt()
        if op == 'fork':
            if pending:
                raise ValueError('flush before branching')
            h.fork(q['name'], revision)
            return receipt()
        raise ValueError('unknown operation')

    print(json.dumps({'ok': True, 'value': receipt()}), flush=True)
    while True:
        line = sys.stdin.buffer.readline(FRAME+1)
        if not line:
            return
        if len(line) > FRAME or not line.endswith(b'\n'):
            raise ValueError('frame exceeds bound')
        try:
            q = json.loads(line)
            result = dispatch(q)
            answer = {'ok': True, 'value': result}
        except Exception as e:
            # Fail closed: the caller must reopen after a rejected operation.
            print(json.dumps({'ok': False, 'error': type(e).__name__ + ': ' + str(e)}), flush=True)
            return
        print(json.dumps(answer, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    path, branch, *geometry = sys.argv[1:]
    h = GroundHistory(path, pages=int(geometry[0]) if geometry else None)
    try:
        serve(h, branch)
    finally:
        h.close()
