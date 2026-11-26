# Virtual Layer contract — C0.2

The product preserves conventional computing semantics while admitting different realizations underneath them. Linux and unkernel are scaffold and reference; original RV32 remains a controlled research implementation. Use the following vocabulary in new components; upstream ABI names remain at adapters and upstream source is not mechanically renamed.

| VL term | Kernel meaning |
|---|---|
| Intention | Typed requested operation, target observation, constraints and resource budget |
| Ground | Admitted domain, generative/transition law, observation function and invariants |
| Ground version | Changes to law/domain or semantic contract, not each state transition |
| State revision | A particular committed state under a fixed Ground version |
| Coordinate | Logical location in an admitted Ground (byte offset, instruction coordinate, etc.) |
| Observer | Entity with an admitted projection or query |
| Interpreter / realization | Concrete implementation that answers a query or realizes a transition |
| Structural memory | Exact sufficient representation retaining required observations |
| Observation digest | Hash of canonical observable bytes; not authority or proof of arbitrary semantic equivalence |
| Receipt | Scoped record binding identity, version, state revision, observation/effect and evidence; this disk receipt is unsigned local metadata |
| Admission | Receiver-owned checks for capability, preconditions, constraints and evidence |
| Pathway | Typed communication route; not inherently an executable operator |
| Authority | Entity permitted to commit effects or change state; not inferred from a content digest |
| Fallback | Conventional realization preserving the admitted contract when optimization is unqualified |

Alignment: VGI's [Ground Versioning and Migration](https://github.com/Kier73/Virtual-Ground-Interpreter/blob/main/virtual_ground/build_21/GROUND_VERSIONING_AND_MIGRATION.md) distinguishes changes to the generative law from state evolution. E-CPU's [Substrate-adaptive observer-host bootstrap](https://github.com/Kier73/E-CPU/blob/main/docs/SUBSTRATE_ADAPTIVE_BOOTSTRAP.md) separates intention, receiver admission, operator bindings, pathways and evidence from authority. IFS operation-span accounting, VL-64 typed observation/admission and VL-I predictive Grounds remain reference contracts; no interoperability claim until tested through actual operators.

## C0.2 — Durable block Ground

GroundDisk is an original Node/POSIX synchronous single-writer realization of the upstream BlockDevice ABI. Ground version vlk.block-ground.v1 fixes exact logical bytes, aligned reads/writes and durable flush. Capacity 4096-byte multiple up to 64 MiB. Live pages remain the existing structural disk; encoding interns equal page representations and coalesces contiguous coordinates with equal object references. No live deduplicated backing claim. Format VLKGRD01: 80-byte header (size u32, state revision u32, 16-byte disk identity, object/run counts u32, 32-byte SHA256 of complete logical bytes, eight reserved zero bytes); objects are u16 length + pattern (1..16 bytes) or 4096 dense bytes; runs are start/count/object-index u32 triples. Absent pages are zero. Final 32 bytes SHA256 of encoded body. Decoder checks bounds, distinct nonzero representation objects, run order/nonoverlap, referenced objects, exact lengths, encoding digest and reconstructed logical digest. SHA256 alone is not authentication, and decoder does not certify a minimal/canonical representation.

Publication is write temporary file, fsync file, rename, fsync parent directory. Initial revision 0; successful flush after a write increments revision; clean flush does not. Receipt reports committed observationDigest and dirty bit; dirty live reads need not match that digest. A distinct disk identity can share a logical digest. No revision history is retained, and a copy can duplicate identity. Trusted exclusive writer assumed; no lock, fencing, adversarial path handling, distributed authority, rollback protection, signatures, snapshotState or snapshotSeal. After uncertain post-rename failure the object refuses further operation until reopened. Crash during fsync/rename, storage power loss, concurrent writers, and adversarial forgery of both digests are not qualified. Temporary files may remain after a kill during publication. Flush tracking resolves after successful subsequent flush; pending waiter cleanup depends on caller lifetime. Synchronous full-disk reconstruction and full encoding per dirty flush cost O(logical size + encoded size), not constant-time navigation.

Local evidence: node compat/unkernel/ground-test.mjs passed initial 112-byte zero image, 133-byte complete durable encoding for 2 MiB periodic disk (one object, one run), full independent logical byte hash and byte comparisons after reopen. Clean flush preserved revision; fresh subprocess SIGKILL before flush retained old commit, after flush retained new commit; distinct disk identities same observation digest; corrupted encoding and rehashed false logical digest refused; size mismatch refused. Existing 3000-operation scatter/gather oracle passed. No full original kernel regression. No Node 24 JSPI or ext4 tooling locally. Linux C0.1 CI remained queued at review. New ground-linux.mjs syntax checked, not executed; CI formats a disposable 16 MiB ext4 disk, mounts over GroundDisk in actual Alpine, writes 64 KiB, unmounts and syncs, reopens and mounts in a new VM, and compares bytes. No real guest or filesystem qualification yet.

Next: complete C0, qualify the Linux acceptance gate and persistent packages. Refine publication into incremental content-addressed objects and persistent revision index; introduce receiver-owned authority and E-CPU transport with fenced publication; measure total realization and verification costs. Then reuse the same contract for memory, snapshots and decoded processor regions.
