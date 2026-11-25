# Validation — 2026-11-25

Local build: C11 native shared library and 6076-byte WebAssembly module, zero imports. K0: 1000 native + 1000 WASM random scalar trajectories, lifecycle, stale handle, budget, reconstruction. K1: 2000 native + 2000 WASM generated affine programs each evaluated in reference, Ground and auto modes against separate host-language reference. Nonlinear fallback and rejected forced Ground; exact budget boundaries, bad instruction checks, empty block and full u64 coordinate.

Trillion repetitions of addr R0,R1; addr R1,R0 from [0,1,0,0] returned [1115770309,906757858,0,0], charged 5210 units. Independently checked by Fibonacci fast doubling in tests/k1.mjs. JSON command also executed successfully. No claim of measured wall-clock speedup, general nonlinear shortcut, production isolation or full OS compatibility. Repository build should independently run make test.
