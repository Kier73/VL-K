# K3.0 — Conventional machine code and independent boot target

## Hosted ELF execution

make all builds dist/vlk-elf; vlk elf FILE [ARG...] runs an ELF32 little-endian static RISC-V executable with e_flags=0, no dynamic interpreter, dynamic segment or TLS segment. The original instruction stream is interpreted directly, not executed by the Linux host. RV32I integer instructions and M integer multiply/divide are implemented, with naturally aligned data accesses, four-byte instruction alignment and no compressed, floating-point, vector, CSR or privileged instructions. FENCE is a no-op in the single-threaded interpreter. Unsupported encodings trap; precise architectural trap state for every fault is not implemented.

The loader uses bounded ELF program headers and PT_LOAD segments, zero-filled BSS, read/write/execute page permissions and a 64 KiB stack, within a 4 MiB flat guest address space. Page-overlapping segments, writable executable pages, null-page mappings, invalid entry points and out-of-bounds segments are rejected. It creates a 16-byte-aligned initial stack with argc, argv, null envp and AT_NULL only. No dynamic linker, relocations, full Linux auxiliary vector, mmap, threads, signals, filesystem or general libc ABI. Guest environment is empty. Each image has one fresh address space. Hosted syscall subset: RV Linux read(63) fd0, write(64) fd1/fd2, exit(93), exit_group(94), brk(214); unknown calls return -ENOSYS. Invalid descriptor or memory buffer returns -EBADF/-EFAULT. Host forwards only bounded stdio buffers. brk grows and shrinks bounded heap page mappings, not a full Linux VM implementation. Hosted runner has 100 million instruction budget; blocking I/O is not time-bounded. This is a compatibility bootstrap, not a security sandbox or complete RISC-V/Linux conformance claim.

examples/rv32/demo.c and filter.c compile from the same source to native host and RV32IM ELF, using a small freestanding entry and standard syscall numbers on RISC-V. No binary rewriting. These are new test applications, not unmodified third-party Linux executables. Standard executables with requirements outside this admitted ABI are refused or trap.

## Freestanding PC kernel

make boot produces dist/vlk-boot.elf: static ELF32 i386 Multiboot v1 image with a 32-bit entry, private stack, polled COM1 UART, embedded RV32 application and the same src/rv32.c used by the hosted runner. No Linux syscalls or host libc in this target. Multiboot bootloader supplies protected-mode flat segments and loaded ELF segments. Kernel checks boot magic, runs the embedded ELF, then exposes a serial help, run, halt monitor. The halt command stops the CPU; QEMU must be terminated externally. No filesystem, guest dynamic application loading from disk, hardware interrupt controller, MMU, scheduler, networking or native PC user ABI yet. It is a bootloader-loadable freestanding kernel target, not a self-loading firmware or standalone full OS.

Run make boot-test on a machine with qemu-system-i386 or qemu-system-x86_64. Alternatively qemu-system-i386 -m 32M -display none -monitor none -serial stdio -kernel dist/vlk-boot.elf. The boot CI workflow runs the real emulator and asserts the serial startup, expected guest checksum, interactive help, second guest execution and halt command. Local environment has neither QEMU nor /dev/kvm; runtime boot is unverified locally. Static validation checked Multiboot header within first 8 KiB, checksum, ELF class/type/machine, no unresolved symbols, and exact embedded guest image. Local sizes: boot ELF 29412 bytes, demo ELF 8792 bytes (file sizes, not runtime resident memory; RAM array 4 MiB).

## Validation

Local build and execution through VL-K: 40 generated argument workloads matched native demo binary; 1 MiB pseudorandom binary filter output matched native and independent byte XOR; assembly ABI test verified ENOSYS/EBADF/EFAULT, brk growth/shrink/regrowth, signed overflow and divide-by-zero behavior, multiply-high signed/unsigned corner cases, and exit 23. Eight malformed ELF inputs and four execution/access traps rejected. Positive and negative portions passed across split runs due execution timeout. Full prior regression suite not rerun in this pass. Direct E-CPU checkout remains blocked by local DNS. No actual full Linux applications or remote E-CPU runtime execution claimed.

## Next conventional milestones

1. Run the QEMU boot acceptance test, retain actual transcript, then add interrupts/timer, physical memory map and storage/device drivers.
2. Expand RV ELF loader to ordinary static libc applications (auxv, brk/mmap/munmap, openat/read/write/close/fstat/lseek, clock and signal basics), qualify with independently developed static binaries and ABI conformance tests.
3. Add process isolation, scheduling and resource ownership under bare metal; shared interface with hosted runtime, then filesystem, terminal and networking.
4. Run a real third-party research application (e.g. SQLite CLI or a compiler/interpreter) inside the guest, not via host exec. Use actual workloads as optimization candidates only after conventional semantics are established.
5. Introduce existing Virtual Layer Grounds beneath the machine-code execution path using verified register/memory/effect equivalence; conventional fallback remains the baseline.
