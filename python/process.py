"""Hosted process table. A single owner controls direct children, not arbitrary PIDs."""
import os
import subprocess
from dataclasses import dataclass

PIPE = subprocess.PIPE
DEVNULL = subprocess.DEVNULL
STDOUT = subprocess.STDOUT


@dataclass(frozen=True)
class Status:
    handle: int
    pid: int
    returncode: int | None


class Supervisor:
    def __init__(self, capacity=64):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('positive capacity required')
        self.capacity = capacity
        self._next = 1
        self._children = {}
        self._closed = False

    def spawn(self, argv, *, stdin=None, stdout=None, stderr=None, cwd=None, env=None):
        if self._closed:
            raise RuntimeError('supervisor closed')
        if len(self._children) >= self.capacity:
            raise RuntimeError('process table full')
        if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(x, str) for x in argv):
            raise ValueError('expected nonempty argv of strings')
        p = subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=stderr,
                             cwd=cwd, env=env, close_fds=True)
        h = self._next
        self._next += 1
        self._children[h] = p
        return h

    def pipeline(self, commands, *, stdin=None, stdout=None, stderr=None, cwd=None, env=None):
        """Connect commands with owned OS pipes; return ordered child handles."""
        if self._closed:
            raise RuntimeError('supervisor closed')
        if not isinstance(commands, (list, tuple)) or not commands:
            raise ValueError('expected nonempty command sequence')
        if len(commands) > self.capacity - len(self._children):
            raise RuntimeError('process table full')
        if stdin == PIPE or stderr == PIPE:
            raise ValueError('pipeline stdin/stderr require inherited streams or files')
        handles, owned = [], set()
        previous = stdin
        try:
            for i, argv in enumerate(commands):
                last = i == len(commands)-1
                if last:
                    output, next_input = stdout, None
                else:
                    next_input, output = os.pipe()
                    owned.update((next_input, output))
                h = self.spawn(argv, stdin=previous, stdout=output, stderr=stderr,
                               cwd=cwd, env=env)
                handles.append(h)
                if isinstance(previous, int) and previous in owned:
                    os.close(previous)
                    owned.remove(previous)
                if isinstance(output, int) and output in owned:
                    os.close(output)
                    owned.remove(output)
                previous = next_input
            return tuple(handles)
        except BaseException:
            for fd in owned:
                os.close(fd)
            for h in handles:
                self.kill(h)
            for h in handles:
                self.wait(h)
                self.release(h)
            raise

    def _get(self, handle):
        if type(handle) is not int or handle not in self._children:
            raise KeyError('unknown process handle')
        return self._children[handle]

    def status(self, handle):
        p = self._get(handle)
        return Status(handle, p.pid, p.poll())

    def wait(self, handle, timeout=None):
        return self._get(handle).wait(timeout=timeout)

    def communicate(self, handle, data=None, timeout=None):
        return self._get(handle).communicate(input=data, timeout=timeout)

    def terminate(self, handle):
        p = self._get(handle)
        if p.poll() is None:
            p.terminate()

    def kill(self, handle):
        p = self._get(handle)
        if p.poll() is None:
            p.kill()

    def release(self, handle):
        p = self._get(handle)
        if p.poll() is None:
            raise RuntimeError('cannot release running child')
        for f in (p.stdin, p.stdout, p.stderr):
            if f is not None:
                f.close()
        del self._children[handle]

    def close(self):
        self._closed = True
        # Kill direct children before waiting, so cleanup does not depend on cooperation.
        for h in list(self._children):
            self.kill(h)
        for h in list(self._children):
            self.wait(h)
            self.release(h)

    def __enter__(self):
        if self._closed:
            raise RuntimeError('supervisor closed')
        return self

    def __exit__(self, *exc):
        self.close()
