"""Receiver-owned pure observation service; independent of transport and migration."""
from debugger import Session, coordinate
from loop_receipt import canonical, digest

OPERATION = 'observe VL-K pure guest coordinate'
RESOURCE = '/cpu/vlk/observe'
RIGHTS = frozenset({'execute'})


def request(program, tick):
    s = Session(program)
    return {'version': 1, 'program_sha256': s.identity, 'tick': str(coordinate(tick))}


def tick_of(payload):
    if type(payload) is not dict or set(payload) != {'version','program_sha256','tick'} or type(payload['version']) is not int or payload['version'] != 1:
        raise ValueError('invalid observation request')
    identity, tick = payload['program_sha256'], payload['tick']
    if type(identity) is not str or len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
        raise ValueError('invalid program identity')
    if type(tick) is not str or not tick.isascii() or not tick.isdecimal() or len(tick) > 20 or str(int(tick)) != tick:
        raise ValueError('invalid tick encoding')
    return coordinate(int(tick))


class ObservationHost:
    def __init__(self, programs, *, max_tick):
        self._max_tick = coordinate(max_tick)
        self._programs = {}
        for program in programs:
            s = Session(program)
            self._programs[s.identity] = s.program

    def observe(self, payload):
        t = tick_of(payload)
        if t > self._max_tick or payload['program_sha256'] not in self._programs:
            raise ValueError('coordinate or program not admitted')
        s = Session(self._programs[payload['program_sha256']])
        s.advance(0, t)
        body = {'version': 1, 'request_sha256': digest(payload), 'checkpoint': s.checkpoint()}
        return {'body': body, 'sha256': digest(body)}

    def handle(self, event):
        """E-CPU handler: event must have been authorized by receiver's capability gate."""
        from mailcpu.classifier import HypervisorArbitrationEvent
        if not isinstance(event, HypervisorArbitrationEvent):
            raise ValueError('typed arbitration event required')
        r = event.request
        if r.operation != OPERATION or r.resource != RESOURCE or r.required_rights != RIGHTS or r.granted_rights != RIGHTS or r.destructive:
            raise ValueError('receiver-local observation authority required')
        return self.observe(r.payload)


def verify(result, payload, program):
    """Reconstruct using pinned local program, reject forged values even with new hashes."""
    try:
        t = tick_of(payload)
        s = Session(program)
        if s.identity != payload['program_sha256']:
            return False
        expected = ObservationHost([program], max_tick=t).observe(payload)
        return canonical(expected) == canonical(result)
    except (ValueError, TypeError, RuntimeError, KeyError, IndexError, OverflowError):
        return False
