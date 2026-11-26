# Conventional substrate — unkernel parity and bottom-up replacement

Audit pins: VL-K cbf83fecb29611f46652905c81a7a708a584de7f; unkernel fd204d3130309c45ce51795c753c3b8ec1eaddfd (release v0.2.0-261126-fd204d3). Reviewed upstream README, kernel/README, package.json, THIRD-PARTY, source tree, js/core/{instance,kernel,block,net,snapshot,tty}.ts, js/node.ts, js/node/distro-fetch.ts, .agents/testing.md and test/api.test.ts. Upstream capabilities are documented/source-inspected, not locally reproduced.

## Product target

A real computer is a usable environment for arbitrary computation within supported architecture, resource and device limits: terminal and desktop, persistent files, installation and execution of unmodified applications, standard libraries, concurrency, networking, clocks, randomness, graphics/audio/input, development tools and reproducible session management. Physical bare-metal boot is a separate platform target. No finite implementation supports every binary, architecture or peripheral.

| Area | unkernel | VL-K original core |
|---|---|---|
| Kernel | Linux 7.3.4 patched arch/wasm, compiled to WASM | original C RV32IM interpreter and bounded Linux-number syscalls |
| Application ABI | AArch64 distro binaries, FP/AdvSIMD, crypto, LSE, dynamic loaders | static RV32IM ELF, no standard libc qualification |
| Processes | Linux scheduler, signals, threads, namespaces, cgroups, epoll, ptys, SMP | two flat or four pooled slots, cooperative slices, clone/exec/wait/pipes, limited shell |
| Memory | Sv48 MMU, Linux VM/COW/shared memory | 4 MiB logical spaces, pairwise COW or bounded shared zero/periodic/dense pool |
| Files | ext4/overlayfs/tmpfs/FUSE/9p, persistent data disk | eight flat files, 256 KiB each; structural volumes in single-ELF runner, session modes/data volatile |
| Devices | block, TCP/DNS transport, vsock, shmem, framebuffer, evdev, audio, virtio, GL/Wayland | standard streams, serial monitor and in-memory pipes |
| User environment | Alpine/Debian, package managers, Python/Node, browser desktop | guest-created ELF installation and small postfix compiler; no unchanged distro package |
| Deployment | JS SDK, browser/worker/Node, release bundles, HTTP-range disks | native launcher (host passthrough is not guest capability), C/WASM mathematical nucleus, i386 Multiboot target statically built but actual boot unverified |
| Continuity | parked snapshot, build/device/CPU/disk-generation checks; TCP/vsock reset | pure-guest observation/debug/authority and fenced effects; no complete RV32 machine snapshot |
| Adaptive compute | decoded ops + WASM JIT | exact affine/weighted temporal Grounds, structural memory and independent realization experiments, not integrated with Linux ABI |

Unkernel host networking has IPv4/TCP-oriented limitations: no arbitrary UDP or IPv6, inbound service access through vsock forwarding. Upstream benchmarks are not cross-system measurements.

## Adopt first; refactor beneath stable contracts

Maintain two distinguished execution targets: original research kernel and pinned Linux compatibility substrate. Start with the unmodified released SDK/kernel; import a complete upstream source tree or maintain a pinned fork/submodule when source-level changes are needed. Preserve history, notices and build provenance. Avoid cherry-picking tightly coupled Linux architecture patches, emulator and device code. Adopt upstream CLI/SDK, rootfs, devices and tests rather than rebuilding equivalent facilities.

Licensing: upstream THIRD-PARTY.md identifies its core as GPL-2.0-or-later, Linux as GPL-2.0, SDK and web page as MIT, and third-party components separately. package.json states MIT AND GPL-2.0-only for combined distribution. VL-K has no selected license. Downloading an unmodified upstream package as an external dependency is the initial route; no upstream code copied or combined artifact published here. Before copying/combining/distributing, decide licensing policy, preserve per-file SPDX/notices, provide required corresponding source and build materials for GPL distributions, and review component boundaries. Separate directories do not automatically exempt combined work.

## Acceptance gates

C0: Actual Linux boot and guest execution on Node 24+ with JSPI. Pinned prepare.sh verifies upstream package and Alpine image against release SHA-256. smoke.mjs checks guest /proc and architecture, pipeline, 64 KiB binary file roundtrip against host hash, exit/stderr and concurrent commands. No network or host mounts. CI must report pass before claiming integration. Local bash/JS syntax checks passed; Node 22.16.0 lacks JSPI and preflight correctly exits 2. GitHub DNS unavailable locally; no local download or boot. Guest acceptance unexecuted.

C1: Stable VL-K backend/session API (spawn/exec/streams, status, resource limits, capabilities, stop). Add persistent ext4 data disk, clean shutdown/reopen, application installation and session identity. Qualify Alpine Python, SQLite, compiler and original E-CPU from pinned inputs, actually inside guest. Add Debian/dynamic libc. Network opt-in, explicit endpoint and mount authority.

C2: Browser/desktop target, terminal resizing/signals, file management, display/input/audio, GL/Wayland, package manager and network; reuse upstream components. Verify Node and supported browsers/workers, storage persistence and device limitations. Physical native boot separately needs verified QEMU boot, interrupts, clocks, storage/network/platform drivers; consider standard Linux or a VMM before independent driver development.

C3: Exact structural BlockDevice beneath Linux ext4: sector-aligned scatter/gather, bounded representations, flush ordering, read-only/error behavior, persistent disk identity and generations. Compare bytes/file effects to ordinary backend, including random writes, crash/remount. Upstream HTTP ranges/COW already exist; new work is procedural exactness, authority and cost selection. Add authenticated E-CPU NetBackend/vsock or remote block transport, reconnect/replay/fencing and explicit effects. No assumed arbitrary TCP migration or exactly-once effects.

C4: Portable machine state. Use upstream snapshot/disk-generation contract; pin kernel fingerprint, CPU count, device configuration, memory and disk state. Separate representation from snapshot identity, verify restoration and successor observations, reject mismatches on independent hosts. TCP/vsock reset is a limitation.

C5: Processor integration. Retain upstream reference interpreter/JIT. Add exact Ground alternative for closed pure decoded blocks with register/flag/memory equivalence, logical time and interruption boundaries. Do not skip syscalls, exceptions, timers, volatile memory, atomics or effects without qualified proof. Compare total discovery/verification/realization cost. Replace bottom-up only when acceptance and end-to-end benchmarks justify it. Full Linux scheduler/MMU replacement is not a prerequisite.

## Reuse map

- kernel/patches/linux, kernel/build.sh, kernel/tools, guest/: coupled kernel/distro baseline.
- src/a64, src/emu, include/kw_emu.h: reference decoder/JIT and future qualified block dispatch.
- js/core/block.ts, js/node/disk.ts: structural memory insertion; BlockDevice and snapshotState.
- js/core/net.ts, js/core/vsock.ts, js/core/tty.ts: communication and terminals.
- js/core/snapshot.ts, js/core/instance.ts: lifecycle and snapshot consistency.
- js/core/worker*, js/web, web/, gl/, vk/, va/: retain deployment/devices.
- .agents/testing.md, test/api.test.ts and upstream device/emulator tests: compatibility acceptance.

Priority: C0, then C1/C2 while working C3. Original kernel remains independent research/reference. No original implementation change in this audit.
