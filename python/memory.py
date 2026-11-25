"""Byte-addressed memory with immutable page overlays and exact backing laws."""
from bisect import bisect_right
from dataclasses import dataclass

PAGE = 4096
LIMIT = 1 << 64


def span(start, size, limit=LIMIT):
    if type(start) is not int or type(size) is not int or not 0 <= start <= limit or not 0 <= size <= limit-start:
        raise ValueError('invalid address range')
    return start + size


class Memory:
    def __init__(self, size, *, data=None, pattern=None):
        span(0, size)
        if data is not None and pattern is not None:
            raise ValueError('choose one backing')
        self._size = size
        self._data = None if data is None else bytes(data)
        self._pattern = b'\0' if pattern is None else bytes(pattern)
        if self._data is not None and len(self._data) != size:
            raise ValueError('resident backing length mismatch')
        if not self._pattern:
            raise ValueError('empty pattern')
        self._pages = {}

    @property
    def size(self):
        return self._size

    def _base(self, start, size):
        if self._data is not None:
            return self._data[start:start+size]
        p = self._pattern
        offset = start % len(p)
        first = p[offset:offset+size]
        remaining = size-len(first)
        copies, tail = divmod(remaining, len(p))
        return first + p*copies + p[:tail]

    def read(self, start, size):
        end = span(start, size, self.size)
        out = bytearray()
        while start < end:
            page, offset = divmod(start, PAGE)
            n = min(end-start, PAGE-offset)
            if page in self._pages:
                out.extend(self._pages[page][offset:offset+n])
            else:
                out.extend(self._base(start, n))
            start += n
        return bytes(out)

    def write(self, start, data):
        data = bytes(data)
        end = span(start, len(data), self.size)
        pos = 0
        while start < end:
            page, offset = divmod(start, PAGE)
            n = min(end-start, PAGE-offset)
            base = self._base(page*PAGE, min(PAGE, self.size-page*PAGE))
            old = self._pages.get(page, base)
            new = old[:offset] + data[pos:pos+n] + old[offset+n:]
            if new == base:
                self._pages.pop(page, None)
            else:
                self._pages[page] = new
            start += n
            pos += n
        return len(data)

    def fork(self):
        other = object.__new__(Memory)
        other._size, other._data, other._pattern = self.size, self._data, self._pattern
        other._pages = self._pages.copy()
        return other

    def stats(self):
        return {'logical_bytes': self.size,
                'backing_bytes': len(self._data) if self._data is not None else len(self._pattern),
                'overlay_pages': len(self._pages),
                'overlay_bytes': sum(map(len, self._pages.values()))}


@dataclass(frozen=True)
class Mapping:
    start: int
    memory: Memory
    writable: bool
    shared: bool

    @property
    def end(self):
        return self.start + self.memory.size


class AddressSpace:
    """Fixed-range mappings; explicit shared or private fork semantics."""
    def __init__(self):
        self._starts = []
        self._maps = {}

    def map(self, start, size, *, data=None, pattern=None, writable=True, shared=False):
        end = span(start, size)
        if not size or type(writable) is not bool or type(shared) is not bool:
            raise ValueError('invalid mapping')
        i = bisect_right(self._starts, start)
        if (i and self._maps[self._starts[i-1]].end > start) or (i < len(self._starts) and self._starts[i] < end):
            raise ValueError('overlapping mapping')
        m = Mapping(start, Memory(size, data=data, pattern=pattern), writable, shared)
        self._starts.insert(i, start)
        self._maps[start] = m

    def unmap(self, start):
        del self._maps[start]
        self._starts.remove(start)

    def protect(self, start, *, writable):
        if type(writable) is not bool:
            raise ValueError('expected boolean protection')
        m = self._maps[start]
        self._maps[start] = Mapping(start, m.memory, writable, m.shared)

    def _segments(self, start, size, write=False):
        end = span(start, size)
        segments = []
        while start < end:
            i = bisect_right(self._starts, start)-1
            if i < 0:
                raise MemoryError('unmapped address')
            m = self._maps[self._starts[i]]
            if start >= m.end:
                raise MemoryError('unmapped address')
            if write and not m.writable:
                raise PermissionError('read-only mapping')
            n = min(end-start, m.end-start)
            segments.append((m.memory, start-m.start, n))
            start += n
        return segments

    def read(self, start, size):
        return b''.join(m.read(offset, n) for m, offset, n in self._segments(start, size))

    def write(self, start, data):
        data = bytes(data)
        segments = self._segments(start, len(data), write=True)
        pos = 0
        for m, offset, n in segments:
            m.write(offset, data[pos:pos+n])
            pos += n
        return pos

    def fork(self):
        other = AddressSpace()
        other._starts = self._starts.copy()
        other._maps = {a: Mapping(a, m.memory if m.shared else m.memory.fork(), m.writable, m.shared)
                       for a, m in self._maps.items()}
        return other

    def stats(self, start):
        return self._maps[start].memory.stats()
