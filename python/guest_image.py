"""Versioned portable guest image, with exact payload length and identity."""
import hashlib
import json
import struct
from debugger import validate, FILE_LIMIT
from loop_receipt import canonical

MAGIC=b'VLKAPP\x01\x00'
HEADER=struct.Struct('!8sI32s')


def pack(program):
    payload=canonical({'program':validate(program,application=True)}).encode('ascii')
    if len(payload)>FILE_LIMIT: raise ValueError('image too large')
    return HEADER.pack(MAGIC,len(payload),hashlib.sha256(payload).digest())+payload


def unpack(raw):
    if len(raw)<HEADER.size: raise ValueError('truncated image')
    magic,n,sha=HEADER.unpack_from(raw);payload=raw[HEADER.size:]
    if magic!=MAGIC or n>FILE_LIMIT or n!=len(payload) or hashlib.sha256(payload).digest()!=sha:
        raise ValueError('invalid image header or digest')
    spec=json.loads(payload)
    if not isinstance(spec,dict) or set(spec)!={'program'}: raise ValueError('invalid image schema')
    program=validate(spec['program'],application=True)
    if pack(program)!=raw: raise ValueError('noncanonical image')
    return program


def load(path):
    with open(path,'rb') as f: raw=f.read(FILE_LIMIT+HEADER.size+1)
    if raw.startswith(MAGIC): return unpack(raw)
    if len(raw)>FILE_LIMIT: raise ValueError('program too large')
    spec=json.loads(raw)
    if not isinstance(spec,dict) or set(spec)!={'program'}: raise ValueError('expected application program')
    return validate(spec['program'],application=True)


def main():
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('program');p.add_argument('output');a=p.parse_args()
    try: Path(a.output).write_bytes(pack(load(a.program)))
    except (ValueError,OSError,TypeError) as exc: p.exit(125,f'pack: {exc}\n')
    return 0

if __name__=='__main__': raise SystemExit(main())
