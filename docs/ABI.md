# Kernel semantics

K0 ABI 1: vk_spawn(kind,seed,a,b), vk_fork(id), vk_exit(id), vk_observe(id,target,budget), vk_advance(id,expected,target,budget), vk_restore(kind,seed,a,b,t,budget), vk_time(id), vk_value(), vk_work(), vk_abi(). Handles are positive, local and monotonically assigned. Kinds 1/2 are affine/quadratic modulo 2^32. Observation is pure, advance is forward compare-and-commit, failure leaves committed state intact. UINT64_MAX is reserved for invalid time. Value is meaningful only after successful evaluation. Single serialized authority.

K1 is an additive ABI extension. Begin with vk1_begin(), set four seeds via vk1_seed(r,value), append instructions via vk1_append(op,d,x). Instructions execute in order, including aliasing. Opcodes: 1 set immediate, 2 copy register, 3 add immediate, 4 multiply immediate, 5 add register, 6 multiply register. Arithmetic is modulo 2^32. Registers indexed 0..3. vk1_run(n,budget,mode) repeats the block n times from seed. Modes 0 automatic, 1 forced reference, 2 forced Ground. vk1_result(r) is meaningful only after success; vk1_work() and vk1_method() report cost and method (0 identity, 1 reference, 2 Ground). WASM n is a BigInt, i32 values are converted to unsigned with >>> 0. All u64 repetition counts are valid for K1. Status 0 success, -1 invalid/unsupported forced Ground, -2 capacity, -3 K0 conflict, -4 budget. Failed K1 evaluation invalidates output. Staging and results are instance-local; callers serialize access.

## Exact Ground

Represent registers and constant 1 as a 5-vector over Z/(2^32). Start with identity matrix. Each instruction updates its destination row in program order: set clears it and writes the constant column; copy copies the source row; add immediate changes constant coefficient; multiply immediate scales row; add register adds source row. Induction on instruction prefixes establishes exact equality with reference evaluation for every input. Register multiplication is conservatively ineligible. Binary powering composes the complete block map, preserving all inter-register dependencies. Empty blocks and zero repetitions realize identity.

For nonzero n and block length L, reference work is n*L instructions; Ground work is 5L + 25*popcount(n) + 125*floor(log2(n)). The model charges coefficient visits and dense multiply-accumulate terms, not measured cycles, excludes bounded analysis/setup and output movement, and is not a hardware gas model. Auto selects the smaller charge, choosing reference on ties. Overflow-safe comparison uses n > ground_cost/L. Check budget before execution. For fixed register dimension navigation is logarithmic in the coordinate; no general nonlinear complexity claim.

## Authority

K1 is a pure evaluation request, not yet lifecycle-integrated. It cannot commit external effects. K0 process authority is not a security boundary against the embedding host. Local process identifiers must not be treated as global capabilities.
