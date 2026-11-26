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

## Weighted Grounds and portable application images

`vlk pack PROGRAM IMAGE` creates a versioned portable guest image; `vlk app IMAGE INPUT AUTHORITY SINK JOB` runs it through the same bounded application contract. Committed output can be delivered to an explicitly pinned sink over mutually authenticated TLS, with retry after receiver death. `python3 tests/weighted_ground.py` exercises weighted selector reduction, including a counterexample where state-only equivalence is insufficient. See [weighted Ground and effect contract](docs/WEIGHTED_BOOTSTRAP.md).

## Constructive temporal refinement

`vlk refine TABLE` admits a sparse duration Ground when a weighted residue table describes a global translation and sparse temporal exceptions; otherwise retains an exact weighted quotient. The service accepts newline JSON `{ "x": 0, "ticks": "1000000", "maximum": "1000000" }`. Ordinary guest loops with equal translations and a single exceptional branch duration can use the sparse clock automatically. See [constructive refinement](docs/REFINEMENT.md).

## Conventional ELF and freestanding kernel

`make all boot` builds a hosted RV32IM ELF runner and freestanding i386 Multiboot image. `vlk elf dist/demo.rv32 kernel` interprets standard compiled machine code; `make boot-test` exercises the independent boot target in QEMU. See [conventional kernel contract](docs/CONVENTIONAL_KERNEL.md) for the admitted ABI and validation boundaries.

## File-backed compiled applications

`vlk elf --volume workspace.vfs dist/file.rv32 put source < input.bin` creates a file inside the guest volume. Use `xor source result` and `get result` with the same volume to transform and retrieve it. The freestanding serial monitor also has a `file` command that increments a file-backed counter in its RAM filesystem. See [guest filesystem contract](docs/GUEST_FILESYSTEM.md).

## Production priorities

[Production roadmap](docs/PRODUCTION_ROADMAP.md): conventional application ABI, independently verified boot and external executable loading, isolated processes and interactive terminals, real upstream research workloads, then reciprocal E-CPU execution and measured adaptive optimization.

## Application runtime and external boot module

`make boot dist/runtime.rv32` builds the freestanding image and separate runtime ABI probe. `vlk elf --env MODE=vlk dist/runtime.rv32 kernel` exercises startup and anonymous memory operations. `make boot-test` additionally attempts to launch the separate ELF supplied as a Multiboot module. See [runtime and module contract](docs/RUNTIME_STARTUP.md).

## Process-local descriptor references

Shared file objects and open descriptions are distinct from process-local descriptor tables. `python3 tests/descriptors.py` qualifies duplication, metadata and interleaved guest contexts. See [descriptor contract](docs/DESCRIPTORS.md).

## Structural file memory

All guest file objects now use exact zero, periodic or dense page backing. `vlk elf --compact-volume FILE ELF [ARG...]` preserves compact representations in VLKFS2; the existing `--volume` selects the compatible dense VLKFS1 output format. Both accept either version as input. See [structural files](docs/STRUCTURAL_FILES.md) and `python3 tests/structural_files.py`.

## Cooperative guest processes

The shared C scheduler manages two independently identified RV32 guests with per-process instruction budgets, private memory and descriptor tables, and shared structural file storage. `python3 tests/rvproc.py` qualifies the lifecycle through actual compiled guests; the freestanding monitor provides `pair` (boot validation pending). See [process contract](docs/GUEST_PROCESSES.md).

## Guest communication and blocked continuations

The shared kernel scheduler connects compiled guests through bounded pipes, suspends blocked read/write instructions without retiring them, and wakes on data, capacity, EOF or peer closure. `python3 tests/rvpipe.py` tests five actual compiled pipelines. See [guest pipe contract](docs/GUEST_PIPES.md).

## Guest-directed sessions

`make all dist/shell.rv32 dist/filter.rv32` then `vlk session dist/shell.rv32 demo=dist/demo.rv32 filter=dist/filter.rv32`. Inside the guest shell use `run demo kernel`, `send abc | filter Q`, or `quit`. See [guest-directed process contract](docs/GUEST_CONTROL.md). The freestanding monitor also provides `guest` (boot validation pending).

## Structural process memory

Fork shares mapped pages without copying payload bytes; writes preserve independent guest observations through exact copy-on-write. `make dist/cow.rv32 && python3 tests/cow.py` exercises compiled guest forks and an eager byte oracle. See [copy-on-write contract](docs/COPY_ON_WRITE.md).

## General page-object memory (component qualification)

`python3 tests/rvobjects.py` qualifies shared zero/periodic/dense page objects across eight address spaces and reserves worst-case private backing before admission. See [page-object contract](docs/PAGE_OBJECTS.md). The live RV32 interpreter still uses the established pairwise COW backend.

## Selectable structural page execution

`make all dist/shell.rv32 dist/filter.rv32` then `dist/vlk-session-objects dist/shell.rv32 demo=dist/demo.rv32 filter=dist/filter.rv32` runs the existing compiled guest shell through the shared page-object backend. See [object runtime contract](docs/OBJECT_RUNTIME.md). The default backend remains unchanged in selection.

## Executable filesystem

The guest shell accepts `install NAME SIZE` followed by exactly SIZE binary bytes, then `run ./NAME ARG` executes the file through the kernel's ELF loader. No catalogue entry is required. See [executable filesystem contract](docs/EXECUTABLE_FILESYSTEM.md). Session files and modes are volatile.

## Guest-hosted compiler

`make all dist/shell.rv32 dist/compiler.rv32` then `./dist/vlk session dist/shell.rv32 cc=dist/compiler.rv32`. Inside the guest, `send in,2,add,out | cc generated` creates a new RV32 ELF; `send A | ./generated` executes it and emits C. See [compiler contract](docs/GUEST_COMPILER.md).

## Conventional Linux compatibility track

A separate pinned unkernel substrate is being qualified as the conventional application environment, preserving the original VL-K research kernel. See [capability comparison and adoption roadmap](docs/CONVENTIONAL_SUBSTRATE.md). The first Linux guest acceptance gate is `bash compat/unkernel/prepare.sh` then `node compat/unkernel/smoke.mjs` (Node 24+ with JSPI; runtime qualification pending).

### Full upstream source and conventional launch

Initialize `git submodule update --init vendor/unkernel` for the pinned complete source. `bash compat/unkernel/prepare.sh` verifies the package, bundled kernel, Alpine and Debian images; `bash compat/unkernel/run.sh alpine` (or `debian`) launches the upstream CLI on Node 24+ with JSPI. `node compat/unkernel/disk-test.mjs` qualifies the new structural block-device component independently. See [bootstrap and evidence](docs/CONVENTIONAL_BOOTSTRAP.md). Actual guest boot remains pending CI.

### Virtual Layer integration contract

[VL terminology and durable block Ground](docs/VL_CONTRACT.md). `node compat/unkernel/ground-test.mjs` qualifies persistent structural encodings and process-loss recovery independently of the Linux scaffold. The Linux ext4 acceptance remains pending runtime qualification.

### Historical coordinate Grounds

`python3 compat/unkernel/ground_history_test.py` exercises a persistent Merkle coordinate index with the unchanged E-CPU PageGroundBacking, historical observations, branching and compare-and-swap publication. See [coordinate Ground contract](docs/COORDINATE_GROUNDS.md). Linux device binding remains pending.

### Historical block pathway

`node compat/unkernel/history-device-test.mjs` exercises the asynchronous BlockDevice adapter over a persistent Python Ground interpreter using native E-CPU page backing. See [historical pathway contract](docs/HISTORICAL_PATHWAY.md). Linux ext4 branch qualification remains pending.

### Portable coordinate witnesses

`node compat/unkernel/coordinate-witness-test.mjs` qualifies independent observation verification, durable store identities and branch seals through the historical pathway. See [portable Ground contract](docs/PORTABLE_COORDINATE_WITNESSES.md).

### Authenticated Ground observation

`python3 compat/unkernel/remote-observer-test.py` qualifies read-only TLS observation and interpreter replacement with detached coordinate verification. The native E-CPU transport adapter is separately gated in CI. See [authenticated observation contract](docs/AUTHENTICATED_OBSERVATIONS.md).

### Observation-realized block projection

`node compat/unkernel/observation-device-test.mjs` exercises a read-only conventional block ABI over verified historical witnesses, certified zero subtrees, bounded cache and local/TLS realization fallback. See [observation realization contract](docs/OBSERVATION_REALIZATION.md).

### Shared computational realization

`make dist/vlk.wasm && node tests/realization.mjs` qualifies the common intention dispatcher over the original WASM execution modes. The observation device uses the same dispatcher for structural derivation, retained pages and verified pathways. See [realization dispatcher contract](docs/REALIZATION_DISPATCHER.md).
