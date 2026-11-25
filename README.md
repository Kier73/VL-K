# VL-K — Virtual Layer Kernel

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
