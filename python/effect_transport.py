"""Bounded authenticated effect delivery to an explicitly pinned SQLite sink."""
import json
import socket
import ssl
import struct
from loop_receipt import canonical, digest
from application import LIMIT

FRAME=2*LIMIT+16384


def receive(conn):
    def exact(n):
        data=bytearray()
        while len(data)<n:
            b=conn.recv(n-len(data))
            if not b: raise EOFError('incomplete frame')
            data.extend(b)
        return bytes(data)
    n=struct.unpack('!I',exact(4))[0]
    if not 0<n<=FRAME: raise ValueError('invalid frame length')
    return json.loads(exact(n))


def send(conn,value):
    b=canonical(value).encode('ascii')
    if not 0<len(b)<=FRAME: raise ValueError('invalid frame length')
    conn.sendall(struct.pack('!I',len(b))+b)


class RemoteSink:
    def __init__(self,identity,address,context,server_hostname):
        if type(identity) is not str or len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity): raise ValueError('invalid sink identity')
        if context.verify_mode!=ssl.CERT_REQUIRED or not context.check_hostname or context.minimum_version<ssl.TLSVersion.TLSv1_2:
            raise ValueError('verified TLS required')
        self.identity=identity;self.address=address;self.context=context;self.hostname=server_hostname

    def accept(self,receipt,payload):
        if type(payload) is not bytes or len(payload)>LIMIT: raise ValueError('invalid payload')
        request={'version':1,'sink':self.identity,'receipt':receipt,'payload':payload.hex()}
        with socket.create_connection(self.address,timeout=10) as raw:
            with self.context.wrap_socket(raw,server_hostname=self.hostname) as conn:
                send(conn,request);result=receive(conn)
        if result!={'accepted':digest(request)}: raise ValueError('sink did not acknowledge exact request')


def accept_one(raw,context,expected_peer,sink,*,after_commit=None):
    """One request on an authenticated connection; listener/authorization owned by caller."""
    if context.verify_mode!=ssl.CERT_REQUIRED or context.minimum_version<ssl.TLSVersion.TLSv1_2:
        raise ValueError('mutual TLS required')
    raw.settimeout(10)
    with context.wrap_socket(raw,server_side=True) as conn:
        if ('DNS',expected_peer) not in conn.getpeercert().get('subjectAltName',()): raise PermissionError('peer not authorized')
        q=receive(conn)
        if type(q) is not dict or set(q)!={'version','sink','receipt','payload'} or type(q['version']) is not int or q['version']!=1 or q['sink']!=sink.identity:
            raise ValueError('invalid destination or request')
        if type(q['payload']) is not str: raise ValueError('invalid output encoding')
        payload=bytes.fromhex(q['payload'])
        if len(payload)>LIMIT or payload.hex()!=q['payload']: raise ValueError('invalid output payload')
        receipt=q['receipt']
        if type(receipt) is not dict or set(receipt)!={'job','program_sha256','input_sha256','output_sha256','steps'} or any(type(receipt[k]) is not str or len(receipt[k])!=64 or any(c not in '0123456789abcdef' for c in receipt[k]) for k in ('program_sha256','input_sha256','output_sha256')) or type(receipt['steps']) is not int or not 0<receipt['steps']<=2000000:
            raise ValueError('invalid receipt')
        sink.accept(receipt,payload)
        if after_commit is not None: after_commit()
        send(conn,{'accepted':digest(q)})
