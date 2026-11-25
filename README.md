# VL-K — Virtual Layer Kernel

Run programs through an ordinary command interface. The backend can choose exact alternative execution methods when available; application output is independent of that choice.

```sh
make test
export PATH="$PWD/dist:$PATH"
vlk shell
vlk run python3 -c 'print("hello")'
./examples/fib.vlk 1000000000000
./examples/fib.vlk 10 | cut -d ' ' -f 1
```

The native launcher avoids loading Python for ordinary commands; portable executables use the Python adapter. The hosted command layer uses the underlying POSIX system for conventional programs and shell facilities. Portable VL-K executables use the kernel's exact instruction evaluator. A standalone guest OS, ELF loader and autonomous device layer are development targets. See [execution contract](docs/EXECUTION.md).

A freestanding computational nucleus for portable, navigable execution. K0 provides process lifecycle and exact scalar Grounds; K1 extracts affine Grounds directly from register instructions. The same C11 source builds to a Linux shared library and import-free WebAssembly.

## Use

Requirements: make, C11 compiler, clang with wasm-ld, Python 3, Node 18+.

```sh
make test
echo '{"seed":[0,1,0,0],"program":[["addr",0,1],["addr",1,0]],"steps":1000000000000}' | python3 python/vlk.py
```

Expected: {"status":0,"registers":[1115770309,906757858,0,0],"method":"ground","work":5210}.

Python: add the repository's python directory to your import path, then use vlk.Kernel().evaluate(seed, program, steps, budget=100000, mode="auto"). C/WASM: see src/vlk.h and docs/ABI.md.

The K1 evaluator supports 4 unsigned 32-bit registers, 64 instructions per repeated block, a 64-bit repetition count, and explicitly budgeted exact execution. These are bootstrap implementation parameters. Its pure staging API is serialized per instance. K0 maintains independent process handles; K1 is presently a stateless request evaluator, not yet a K0-managed process.

## Development

- [ABI, mathematical semantics and accounting](docs/ABI.md)
- [Roadmap and integration contracts](docs/ROADMAP.md)
- [Validation](docs/VALIDATION.md)

Original implementation informed by the architectural separation in [unkernel](https://github.com/pithings/unkernel), examined at tree 96e4bd7ebb54b93ad5ec68feab4eda94b3073927. No upstream code copied; no license selected yet for VL-K. Third-party reuse rights need to be established explicitly.

## Browser / Node adapter

```js
import {createKernel} from './js/vlk.mjs';
const kernel = await createKernel(await (await fetch('./dist/vlk.wasm')).arrayBuffer());
const result = kernel.evaluate({seed:[0,1,0,0],program:[['addr',0,1],['addr',1,0]],steps:'1000000000000'});
```

In Node use readFile instead of fetch for a local binary. Coordinates may be exact BigInts, safe integers or canonical decimal strings. Each adapter has an independent WASM instance. The Node adapter tests also exercise invalid input and budget failure. Browser deployment requires serving the built WASM; no live browser test has been conducted.

## Managed processes

```python
from process import Supervisor, PIPE
with Supervisor() as s:
    p = s.spawn(["python3", "-c", "print(42)"], stdout=PIPE)
    output, _ = s.communicate(p)
    assert s.wait(p) == 0
    s.release(p)
```

Add the repository's python directory to the import path. The same API accepts portable executables (put dist on PATH) and ordinary programs. Run `python3 examples/selfbuild.py` to build and validate VL-K under its own hosted process supervisor. See [process contract](docs/PROCESS.md).

Managed pipelines use the same executables and OS streams:

```python
with Supervisor() as s:
    stages = s.pipeline([["printf", "hello"], ["tr", "a-z", "A-Z"]], stdout=PIPE)
    output, _ = s.communicate(stages[-1])
    assert output == b"HELLO"
    assert [s.wait(p) for p in stages] == [0, 0]
```

## Byte-addressed memory

```python
from memory import AddressSpace
space = AddressSpace()
space.map(0x1000, 1 << 40, pattern=b"abcde")
space.write(0x1000, b"hello")
assert space.read(0x1000, 5) == b"hello"
child = space.fork()
child.write(0x1000, b"world")
assert space.read(0x1000, 5) == b"hello"
```

Resident, zero-filled and periodic backing share the same read/write interface. Private mappings fork by sharing immutable pages and copying the overlay index; shared mappings retain common storage. See [memory contract](docs/MEMORY.md). These are software address spaces, not hardware page tables.

## Stress and measurement

`make test` includes randomized state-machine tests against an eager byte oracle, Linux mmap differential checks, SQLite database reconstruction and a test-only guest checksum workload verified by zlib. `python3 benchmarks/memory_reads.py` reports local read timings and verifies the same digest for each backend. Compact memory is not assumed to outperform conventional memory on dense accesses.

## Guest programs and conditional paths

```sh
export PATH="$PWD/dist:$PATH"
printf 'Hello, VL-K' | vlk guest examples/guest-echo.json
```

The guest ISA includes eight u32 registers, ordinary branches, byte memory access, binary streams and exit status. Repeated pure conditional blocks can use automatic exact finite-selector navigation. See [guest and layered path contract](docs/LAYERED_PATH.md). Native host commands still use their existing execution path. This is not a Linux-compatible guest loader yet.


## Automatic optimization of ordinary guest instructions

`vlk guest examples/guest-conditional.json --budget 1600009` runs a conditional countdown program without explicit Ground instructions. Eligible pure loops are discovered and navigated behind the same interface, preserving logical instruction budgets. See [automatic lifting](docs/AUTOMATIC_LIFT.md); `python3 benchmarks/guest_lift.py` compares the two execution modes using the actual CLI and process supervisor.

## Weighted guest paths

`vlk guest examples/guest-weighted.json --budget 32212254729 | od -An -tu1` executes an unannotated unequal-branch guest program. The optimizer preserves logical instruction coordinates, including interruption inside a branch. See [weighted temporal Grounds and receipts](docs/WEIGHTED_PATH.md).

## Interactable pure guest debugger

`vlk debug examples/guest-debug.json` accepts status, observe T, step N, save PATH and quit. Resume with `vlk debug PROGRAM --restore PATH`. The pure session can inspect exact logical coordinates without changing committed state and can reconstruct a verified checkpoint from the original program. See [debugger contract](docs/DEBUGGER.md). General effectful guest execution remains available via vlk guest.

## Transportable pure observations

`python3 tests/observation.py` exercises a receiver-owned program catalogue, a real mutually authenticated loopback TCP exchange and fresh-process continuation from a verified checkpoint (requires OpenSSL). See [observation contract](docs/OBSERVATION.md). E-CPU handler adapter is provided for subsequent integration testing.

## Persistent pure-process authority

`python3 tests/authority.py` exercises SQLite-backed epoch fencing, competing VL-K-launched processes, hard-kill recovery and a native SQL publication consumer. See [authority contract](docs/AUTHORITY.md).

## Reciprocal E-CPU bootstrap

See [bootstrap experiments](docs/BOOTSTRAP.md). The pinned standalone RRNS utility passed cross-implementation tests through VL-K. The reciprocal workflow is an additional integration target for the full E-CPU runtime and reliable-channel observation adapter.

## Durable guest applications and Ground research

`vlk app examples/guest-file-xor.json input.bin authority.db output.db job-001` executes a bounded guest file transformation and publishes its output to a transactional sink. `vlk ground TABLE` discovers an exact reduced residue selector and serves newline JSON observations. See [application and research contract](docs/APPLICATION_BOOTSTRAP.md). `python3 tests/quotient.py /path/to/pinned-ecpu` also checks observations against E-CPU's unchanged RRNS utility.
