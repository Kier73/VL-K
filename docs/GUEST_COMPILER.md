# K3.2.10 — Guest-hosted machine-code compilation

Build: make all dist/shell.rv32 dist/compiler.rv32
Run: ./dist/vlk session dist/shell.rv32 cc=dist/compiler.rv32
Or: ./dist/vlk-session-objects dist/shell.rv32 cc=dist/compiler.rv32

    guest> send in,2,add,out | cc generated
    ok
    guest> send A | ./generated
    Cok
    guest> quit

The compiler itself is initially cross-compiled from C. After that bootstrap, source parsing, optimization, instruction encoding, ELF generation, file creation, fchmod, and subsequent executable launch occur through guest machine instructions and guest syscalls. No generated executable template or host-side assembler is used. The guest compiler emits a new 52-byte ELF32 header, 32-byte PT_LOAD header and RV32IM code at 0x10000. The single load segment is read/execute, and generated code uses the existing writable stack for evaluation and I/O.

## Language and bounds

Comma-separated postfix tokens: unsigned decimal literals 0..4294967295, in (read one byte), add/sub/mul/xor/shr/div (binary operators in left/right order), out (consume the single complete expression and write its low byte). Arithmetic is modulo 2^32; shr masks the shift count to 5 bits; unsigned div by zero yields 0xffffffff, following the RV32 DIVU instruction. At least one out is required; multiple independent expressions can be output in sequence. The generated executable exits zero on completion or 70 when a one-byte read/write does not return one. Input reads occur left-to-right and cannot be optimized away merely because their value is irrelevant. There are no variables, loops, arbitrary branches, functions, linker, libc or C source support yet.

The compiler admits at most 1024 non-separator characters, 15 characters per token, 128 expression nodes per output, 2048 machine words total. The current guest shell's command length bound is smaller. All source must parse and code generation complete before creating a new output file. Exclusive create refuses replacement; failed output attempts close/unlink. Destination '-' emits the generated image to stdout for independent inspection, not as a filesystem file. The session filesystem remains volatile and uses the existing single-owner permission model.

## Structural compilation

Constant-only expression subtrees are evaluated at compile time in unsigned 32-bit arithmetic and replaced by literal nodes. Runtime input nodes remain explicit effect boundaries. Code emission recursively evaluates the remaining tree, preserving the ordered effects; there is no general optimization or minimal-code proof. The generated ELF for 12,3,mul,29,add,out is byte-for-byte identical to 65,out (188 bytes), while in,3,mul,29,add,out produces a 312-byte ELF. The dynamic image was extracted, independently parsed, and executed through the separate single-image runner on input 0x0c, returning A.

## Evidence

tests/compiler.py: 40 distinct source programs (9 deterministic boundary cases, 31 seeded randomized trees) per memory backend, 80 generated executions with exact independent Python oracle output. Includes full-width constants, wraparound, shifts/division, multiple outputs and ordered reads. Nine malformed source cases per backend refused before output creation; duplicates do not overwrite; a missing runtime input fails even when multiplied by zero. The generated ELF header and segment are independently inspected, and the constant-folded output equals the literal output byte for byte. Earlier executable-filesystem (12 sessions) and guest control (five pipelines, ten children and shell) regressions passed. make all boot succeeded/up-to-date; no independent boot run, no full-suite claim or standard libc qualification. The compiler is a hosted guest application, not embedded into the boot monitor.

Next: persist generated tools between sessions, add variables and bounded control flow, qualify a larger independent compiler or assembler, and compare structural code generation with an unoptimized reference. The first goal is guest-generated tools that generate further executables, not merely a larger expression evaluator.
