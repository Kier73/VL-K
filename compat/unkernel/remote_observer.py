"""Read-only Ground observations over a mutually authenticated pathway."""
import json
from pathlib import Path
import socket
import ssl
import sys
import time
from uuid import uuid4
from ground_history import GroundHistory

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python'))
from effect_transport import send, receive
from loop_receipt import canonical


def context(directory, name, server=False):
    d = Path(directory)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if server else ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(d / 'ca.crt')
    if name:
        ctx.load_cert_chain(d / (name + '.crt'), d / (name + '.key'))
    return ctx


class ObserverHost:
    """Receiver-owned finite admission; TLS identity alone grants no Ground access."""
    def __init__(self, history, receipt, coordinates):
        if canonical(history.receipt(receipt['revision'])) != canonical(receipt):
            raise ValueError('unadmitted Ground receipt')
        for i in coordinates:
            history._coordinate(i)
        self.history = history
        self.receipt = receipt.copy()
        self.coordinates = frozenset(coordinates)

    def observe(self, q):
        if (type(q) is not dict or set(q) != {'version', 'op', 'nonce', 'receipt', 'coordinate'}
                or type(q['version']) is not int or q['version'] != 1 or q['op'] != 'observe'
                or type(q['nonce']) is not str or len(q['nonce']) != 32
                or any(c not in '0123456789abcdef' for c in q['nonce'])
                or canonical(q['receipt']) != canonical(self.receipt)
                or type(q['coordinate']) is not int or q['coordinate'] not in self.coordinates):
            raise PermissionError('observation not admitted')
        return {'nonce': q['nonce'], 'witness': self.history.witness(self.receipt['revision'], q['coordinate'])}


def request(receipt, coordinate):
    return {'version': 1, 'op': 'observe', 'nonce': uuid4().hex, 'receipt': receipt, 'coordinate': coordinate}


def check_response(q, answer):
    if type(answer) is not dict or set(answer) != {'nonce', 'witness'} or answer['nonce'] != q['nonce']:
        raise ValueError('response not bound to request')
    return answer['witness']  # caller independently verifies against its pinned receipt


def serve_one(listener, ctx, host, *, before_reply=None, native=False):
    if native:
        from mailcpu.mtls_transport import accept_mutual_tls
        channel = accept_mutual_tls(listener, 'worker', 'observer', ctx, expected_peer_dns='observer', max_frame_size=16384)
        try:
            q = native_receive(channel, 'worker', 'observe')
            answer = host.observe(q)
            if before_reply:
                before_reply()
            native_send(channel, 'worker', 'observer', 'witness', answer)
        finally:
            channel.close()
    else:
        raw, _ = listener.accept()
        with raw:
            raw.settimeout(5)
            with ctx.wrap_socket(raw, server_side=True) as conn:
                if ('DNS', 'observer') not in conn.getpeercert().get('subjectAltName', ()):
                    raise PermissionError('peer not admitted')
                answer = host.observe(receive(conn))
                if before_reply:
                    before_reply()
                send(conn, answer)


def native_send(channel, local, peer, op, value):
    from mailcpu.model import Message
    channel.send(peer, Message(sender=local, op=op, body=(canonical(value),)))


def native_receive(channel, local, op):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        msg = channel.poll(local)
        if msg is not None:
            if msg.op != op or len(msg.body) != 1 or type(msg.body[0]) is not str:
                raise ValueError('invalid native message')
            return json.loads(msg.body[0])
        if channel.closed:
            raise EOFError('pathway closed')
        time.sleep(.001)
    raise TimeoutError('observation pathway timeout')


def observe(address, ctx, q, *, hostname='worker', native=False):
    if native:
        from mailcpu.mtls_transport import connect_mutual_tls
        channel = connect_mutual_tls(*address, 'observer', 'worker', ctx, server_hostname=hostname, max_frame_size=16384)
        try:
            native_send(channel, 'observer', 'worker', 'observe', q)
            answer = native_receive(channel, 'observer', 'witness')
        finally:
            channel.close()
    else:
        with socket.create_connection(address, timeout=5) as raw:
            with ctx.wrap_socket(raw, server_hostname=hostname) as conn:
                send(conn, q)
                answer = receive(conn)
    return check_response(q, answer)
