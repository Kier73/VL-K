"""Pinned E-CPU integration target: real reliable channels and local capability gate."""
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from mailcpu import Capability, HeadlessOS, HypervisorArbitrationEvent, HypervisorRequest, ReliableChannel, SocketTransport
from observation import ObservationHost, OPERATION, RESOURCE, RIGHTS, request, verify
from authority import Authority

program=json.loads((ROOT/'examples/guest-debug.json').read_text())['program']
cut=32212254723;end=cut+5
host=ObservationHost([program],max_tick=end)
receiver=HeadlessOS()
worker=receiver.environment.kernel.spawn('vlk-observer',capabilities=(Capability(RESOURCE,RIGHTS),),parent_pid=receiver.environment.init_pid)
denied=receiver.environment.kernel.spawn('wrong-observer',capabilities=(Capability('/cpu/other',RIGHTS),),parent_pid=receiver.environment.init_pid)

def pair(origin,peer,channel):
    listener=SocketTransport.listen('127.0.0.1',0)
    try:
        a=SocketTransport.connect('127.0.0.1',listener.getsockname()[1],origin,peer)
        b=SocketTransport.accept(listener,peer,origin)
    finally:
        listener.close()
    return a,b,ReliableChannel(a,origin,peer,channel),ReliableChannel(b,peer,peer,channel,peer=origin)

a,b,tx,rx=pair('requester','worker','vlk-observe')
c,d,reply,receive_reply=pair('worker','requester','vlk-result')
try:
    q=request(program,cut)
    seq=tx.send((q,))
    assert rx.receive()==(seq,(q,))
    # A sender's asserted rights cannot substitute for the receiver's grants.
    event=HypervisorArbitrationEvent('requester','vlk-observe',seq,0,
        HypervisorRequest(OPERATION,RESOURCE,q,RIGHTS,RIGHTS))
    try:
        host.handle(receiver.hypervisor_authorize_event(denied,event))
        raise AssertionError('unauthorized operation accepted')
    except ValueError: pass
    result=host.handle(receiver.hypervisor_authorize_event(worker,event))
    assert tx.process_ack()==(seq,)
    rs=reply.send((result,))
    received=receive_reply.receive()
    assert received==(rs,(result,)) and reply.process_ack()==(rs,)
    assert verify(received[1][0],q,program)
    with tempfile.TemporaryDirectory() as directory:
        authority=Authority(Path(directory)/'authority.db')
        authority.create('guest','origin',program)
        pub=authority.advance('guest','origin',1,'observe',0,cut)
        assert pub['body']['checkpoint']==result['body']['checkpoint']
        authority.transfer('guest','origin',1,'receiver',cut)
        authority.advance('guest','receiver',2,'finish',cut,end)
        state=authority.head('guest')['checkpoint']['body']['state']
        assert state['halted'] and state['registers'][0]==0 and state['tick']==str(end)
    print('E-CPU reliable request/result channels, local capability admission and verified VL-K continuation')
finally:
    for transport in (a,b,c,d):transport.close()
