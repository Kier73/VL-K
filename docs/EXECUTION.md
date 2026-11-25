# Ordinary execution contract

VL-K exposes conventional commands first. Ground admission, optimization and accounting are backend concerns. Programs should not need to adopt VL vocabulary or change the meaning of stdout, stderr, argv, working directory, environment or exit status to benefit.

## Hosted stage (implemented)

- vlk run COMMAND ARG... replaces the launcher with a host executable using execvp. No implicit shell expansion. Missing executable 127, other launch errors 126. Host permissions and ordinary file descriptors apply. This path is compatibility delegation, not autonomous VL-K execution or sandboxing.
- vlk shell [ARG...] replaces the launcher with /bin/sh. Shell parsing, pipes, redirection, filesystem access and child management belong to the host.
- An executable beginning with the line "#!/usr/bin/env vlk" can contain a version-1 portable program: JSON fields version, seed, program, steps, output. It runs through the exact register evaluator. One optional unsigned decimal argument overrides steps. Output is selected unsigned registers separated by spaces, followed by newline. Successful exit 0; budget failure 1; malformed executable or arguments 2. The application does not print backend metadata.
- VLK_MODE=reference/ground/auto and VLK_BUDGET are research diagnostics, not application-level dependencies. Default automatic selection. Forced reference and Ground are observationally equivalent within their available budgets for admitted pure programs.

Native Linux is the current command target. The launcher uses Python for bootstrap simplicity, so adds startup overhead and is not a complete POSIX compatibility guarantee (for example, it restores the signals Python ignores to defaults). It does not optimize opaque native binaries. Portable programs presently implement repeated register blocks, not arbitrary instruction sets. No remote authority, privilege isolation, standalone guest kernel or browser shell is claimed.

## Acceptance plan

1. Ordinary process lifecycle: native PID/exit/wait, streams, signals and resource accounting; distinguish host-delegated and kernel-managed processes.
2. File descriptors, filesystem handles, pipes, terminal, memory objects, virtual clock and scheduler under a common process contract; host fallback until equivalent implementations exist.
3. Guest executable loading: define minimal portable bytecode, then WASM and investigate ELF + syscall ABI. Differential conformance suites for each implemented syscall; unsupported calls must fail explicitly or use authorized host fallback.
4. Backend selection: pure computations can be replaced only by equivalent admitted laws. Effects, observations, interrupts and resource limits delimit safe optimization regions. Never elide externally visible effects, even when final registers agree.
5. Measure startup, wall time, memory, throughput and result equivalence against conventional host tools. Accept optimization only when correct and beneficial under declared cost model; account for setup, verification and transport. No universal speedup claim.
6. Boot independently: device interfaces, memory protection and process isolation; hosted and standalone backends should implement the same user-facing contracts.

Local tests on 2026-11-25: existing native/WASM differential suites, JavaScript adapter, and tests/commands.py passed. Command tests compare binary streams, argv, environment, cwd, shell pipes, filesystem writes, signal exit and direct vs delegated executable output; validate error and budget paths. Trillion-step portable executable returns 1115770309 906757858. Remote CI is independent.
