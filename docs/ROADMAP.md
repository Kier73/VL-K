# Development — original research roadmap

The original K-series outline below is retained for historical context. Current K3.x production priorities and acceptance gates are in [Production roadmap](PRODUCTION_ROADMAP.md).

K0 — scalar process lifecycle, exact navigation, reconstruction. K1 — instruction-to-Ground compiler, cost selection, native/WASM and JSON adapter.

K2 — immutable canonical program identity; per-process register state; pure observation versus compare-and-commit; typed checkpoint and verification receipt; distinguish host attempt from logical process. Expose canonical request/result protocol usable from E-CPU operators without depending on transport. Acceptance: independent reconstruction, stale commits rejected, injected incorrect receipts rejected.

K3 — dependency-directed lifting, constant propagation, polynomial and piecewise candidates, exact admission and fallback. Track construction, evidence, navigation and reference costs separately; retain failed candidates as research evidence. Acceptance: differential tests on held-out trajectories and explicit proof of each admitted family.

K4 — host fabric and authority migration; process epoch fencing, source-pinned laws, reliable effect boundary, receipt reconstruction. K5 — memory objects, streams, scheduler, executable loading, devices, guest shell and compatibility adapters. K6 — self-hosting, benchmark operating-system and research workloads.

Integration surface: JSON or C/WASM scalar ABI first; no reverse dependency on consumers. Consumers can embed a pinned commit. E-CPU transport adapter, VGI certificate verifier, IFS persistent authority, VL-64 compact evaluator and VL-I candidate compiler are future adapters rather than claims of current integration.
