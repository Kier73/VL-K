# Reciprocal bootstrap — VL-K and E-CPU

The two directions remain independently measurable. VL-K's native launcher executes ordinary host applications via exec, including the existing E-CPU Python tools. E-CPU can carry pure VL-K observation requests and results using its reliable channels; receiver-local capability admission must precede invocation. A trusted local authority separately commits a continuation. The proposed integration test does not give a transport message exclusive process authority and does not use the hypervisor arbitration replay ledger yet.

## Executed local evidence

The full E-CPU checkout failed because GitHub DNS was unavailable. Instead, the exact standalone mailcpu/rrns.py file was obtained from E-CPU commit 09a9058a43c139c476609954636e17e7fadcfd37 via the repository connector and reconstructed without changes in temporary local storage. Its Git blob hash cb1d4ba145c584c437bf38f17f2899d50f83728c matched upstream, including all 2975 bytes. No E-CPU source is vendored here.

The actual command dist/vlk run python3 tests/ecpu_rrns.py /tmp/ecpu-pinned passed. E-CPU's modular orbit exponentiation, native VL-K K1 matrix execution and the VL-K path evaluator agreed on 4096 generated affine workloads (2048 small counts independently iterated; 2048 randomly chosen u64 counts). Six residue moduli were used to construct five available observations in shuffled order; 4096 reconstructions from four primary residues and one redundant check matched the original value; corrupting the redundant observation was detected in every case. This is detection, not arbitrary error correction or cryptographic authentication. A further 1024 state-selected paths agreed with E-CPU's affine exponentiation of their independently derived two-step composite. Both exponentiation methods exploit the same algebraic principle; this is cross-implementation validation, not an independent theorem proof.

The managed self-build launched by VL-K passed 13 suites before tool interruption. Weighted lift, debugger, observation and authority passed individually through VL-K afterwards. All 17 current make test suites therefore passed across split local runs, not one uninterrupted self-build.

## Pinned integration target

The reciprocal-bootstrap GitHub workflow checks out E-CPU at the exact above commit, builds VL-K, runs the standalone cross-check, launches E-CPU's actual affine-orbit, recurrence and Transit Compute test suites through VL-K, then runs tests/ecpu_observation.py using E-CPU's real TCP ReliableChannel request/result paths, receiver HeadlessOS authorization and the VL-K pure observation adapter. These are separate acceptance targets. The full E-CPU workflow and reverse integration are unexecuted locally because the full runtime was unavailable. Do not infer success from workflow creation. No remote physical host, production kernel, exclusive distributed authority or externally effectful guest migration is claimed.

## Research consequence

A useful cross-check emerges from residue observations: a reconstructed state can carry independently checkable redundant projections without transmitting its full trajectory. Selectors under machine wrap must still be closed in the actual arithmetic; arbitrary CRT moduli do not supply selector closure. RRNS checks validate a represented integer, not arbitrary execution history or causal authority. The next bootstrap experiment should combine E-CPU's actual effect ledger with a narrow VL-K publication sink under authenticated fencing, while preserving ordinary executable and syscall development.
