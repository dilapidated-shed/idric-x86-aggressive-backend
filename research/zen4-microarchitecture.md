# Zen 4 microarchitecture and the current x86 execution target

Status: research and target evidence. This document is deliberately separate from the x86 ISA inventory. An instruction being architecturally available does not say how this processor fetches, predicts, renames, schedules, executes, caches, translates, or feeds it.

## Evidence levels

Keep these levels separate when making optimization decisions:

1. **Observed target contract** — what the current KVM guest actually exposes through Linux and CPUID-derived flags.
2. **AMD processor documentation** — facts from AMD's Zen 4 Software Optimization Guide, EPYC architecture/tuning guides, PPRs, and revision guides.
3. **Measured microarchitecture** — latency, throughput, and execution-resource measurements from independent microbenchmarks such as uops.info.
4. **Analytical reverse engineering** — useful explanations from sources such as Chips and Cheese, but not an AMD architectural promise.

Do not promote levels 3 or 4 into an ISA guarantee. Do not infer physical-host topology from a virtual machine's `lscpu` topology.

## Current container snapshot — 2026-09-24

Observed inside the working container:

| Field | Observed value |
| --- | --- |
| architecture | x86_64 |
| model string | AMD EPYC 9V74 80-Core Processor |
| vendor | AuthenticAMD |
| family | 25 = 19h |
| model | 17 = 11h |
| stepping | 1 = B1 |
| hypervisor | KVM, full virtualization |
| guest CPUs | 5 |
| guest threads/core | 1 |
| guest NUMA nodes | 1 |
| physical address bits | 46 |
| virtual address bits | 48 |
| guest-reported L1d | 96 KiB across 3 instances |
| guest-reported L1i | 96 KiB across 3 instances |
| guest-reported L2 | 3 MiB across 3 instances |
| guest-reported L3 | 32 MiB across 1 instance |

The cache-instance counts and the 5-core/1-thread topology are a **guest presentation**, not evidence for the host package topology. CPU0 sysfs even reports its 32 KiB L1 and 1 MiB L2 as shared by guest CPUs 0-1 despite `lscpu` reporting one thread per core; preserve that inconsistency as virtualization evidence rather than "fixing" it into a plausible physical topology. The model/family/stepping and exposed instruction flags are the useful compilation contract; physical contention and cache sharing still require measurements in the running VM. The exact snapshot is retained in `container-target-20260924.md`.

AMD's current EPYC tuning material explicitly gives decimal family/model/stepping 25/17/1 as a Family 19h Model 11h B1 Zen 4 processor identity.

## Guest-exposed instruction features

The 2026-09-24 guest exposes at least:

- scalar/SIMD baseline: MMX, SSE, SSE2, SSE3, SSSE3, SSE4.1, SSE4.2;
- vector/floating: AVX, AVX2, FMA, F16C;
- AVX-512: F, DQ, IFMA, CD, BW, VL, BF16, VBMI, VBMI2, VNNI, BITALG, VPOPCNTDQ;
- integer/bit: POPCNT, BMI1, BMI2, ADX;
- crypto: AES, VAES, PCLMULQDQ, VPCLMULQDQ, SHA-NI, GFNI;
- cache/memory-related instructions: CLFLUSHOPT, CLWB, CLZERO;
- XSAVE family support and the usual modern x86-64 process facilities.

Not exposed in this guest:

- AMX;
- AVX-512 FP16.

This list is a target mask, not a statement that every instruction has attractive throughput. See `zen4-feature-map.md` for the machine-level questions attached to each exposed family.

# Core anatomy

## Instruction supply

Zen 4 has three important ways to supply already-understood work to the backend:

1. a small loop-delivery mechanism for tiny hot loops;
2. a large operation cache for decoded macro-operations;
3. the conventional L1 instruction-cache -> x86 decoder path.

AMD's Software Optimization Guide documents a **6.75K macro-op operation cache**. The operation-cache path can supply substantially more macro-ops per cycle than the legacy decoder path; AMD's public Zen 4 optimization material gives up to **9 macro-ops/cycle** from the op cache and up to **4 x86 instructions/cycle** through the decoders.

Dispatch into the execution engine is narrower than peak op-cache supply: **up to 6 macro-ops/cycle**.

This distinction matters for code generation. A reduction in x86 instruction bytes is not necessarily a reduction in backend work, and a hot loop fitting the op cache can behave very differently from a cold or sprawling sequence that repeatedly goes through fetch/decode.

Independent measurements report a 144-entry loop buffer. Treat that size as measured evidence unless an AMD source for the exact Zen 4 implementation is cited.

## Fetch alignment and branches

AMD's Zen 4 Software Optimization Guide describes naturally aligned 64-byte fetch blocks and warns that branches near block boundaries can shorten usable fetch bandwidth.

Zen 4 has dedicated next-address logic, BTBs, a return-address stack, an indirect-target predictor, a conditional branch predictor, and fetch-window tracking.

AMD documents a branch-misprediction penalty ranging roughly **11–18 cycles**, with about **13 cycles** as the common case, depending on branch type and whether instruction supply comes from the operation cache.

The Zen 4 BTB can represent useful branch pairs in cases that allow two fetches to be predicted in one prediction cycle. This is a hardware fact worth exploiting only after measuring the exact loop shape; it is not a reason to fill code with branches.

For a proposed small-rotation primitive, test at least:

- branch per element;
- predicated/masked vector form;
- unrolled branchless form;
- branch outside a block of multiple rotations.

## Rename, dispatch, and in-flight work

AMD documents the retire-control structure as tracking up to:

- **320 macro-ops in flight in non-SMT mode**;
- **160 macro-ops per thread in SMT mode**.

Zen 4 dispatches up to six macro-ops/cycle into distributed integer, floating/vector, and load/store scheduling resources.

Independent measurement/reverse engineering reports approximately:

- 224 integer physical registers;
- 192 floating/vector physical registers, widened for 512-bit architectural vector state;
- a separate AVX-512 mask-register file;
- 64 store-queue entries;
- an execution load queue smaller than the total number of loads that can remain tracked/in flight.

These measured structure sizes are useful when explaining pressure, but the AMD guide and PMU events should be preferred for a production scheduling decision.

The key consequence is that **dependency depth and state pressure are different constraints**. A compact representation that saves bytes but forces a long serial unpack/convert chain may prevent the 320-entry window from finding independent work. Conversely, a representation using too many simultaneous temporaries can hit physical-register or scheduler limits before the retire window fills.

## SMT resource sharing

The physical Zen 4 core supports SMT2 even though the current guest exposes one thread per reported core.

AMD distinguishes resources that are competitively shared, watermarked, or statically partitioned between SMT threads. Public Zen 4 optimization material identifies items such as scheduler/register-file/cache/TLB resources as shared in different ways, while retire/store/op-queue resources may be partitioned.

Therefore:

- do not use one-thread VM measurements to predict SMT2 contention;
- if the cloud VM later exposes sibling threads, record sibling placement;
- measure whether a co-runner changes operation-cache, cache, TLB, load/store, or vector behavior.

# Integer execution

AMD's public Zen 4 block diagram shows four integer ALU paths, branch-capable integer resources, integer multiply resources, and three address-generation paths.

The backend is **distributed**, not one universal reservation station. Independent scheduling queues feed different execution resources. A sequence can therefore stall because one particular scheduler/resource class fills even while another class has spare capacity.

For compiler work this means that "six-wide dispatch" is only a ceiling. The actual ceiling for a loop is set by the mix of:

- ALU work;
- multiply/divide;
- branches;
- address generation;
- loads/stores;
- vector/scalar transfers.

BMI1/BMI2, ADX, POPCNT and other "bit tricks" must be evaluated by their actual instruction-specific latency/throughput and dependencies, not by extension membership.

# Floating-point and vector execution

## 128/256-bit path

Zen 4 retains a backend fundamentally built around **256-bit vector arithmetic datapaths**.

Independent reverse engineering describes:

- four 256-bit vector ALU-capable paths for common arithmetic/logical work;
- two 256-bit FMA-capable paths;
- separate restrictions for permutations, conversions, moves, and special operations.

Exact routing is instruction-specific. Use AMD's optimization tables and uops.info per instruction rather than assigning every operation to a generic "vector pipe."

## AVX-512 implementation

The current guest exposes a broad AVX-512 feature set, but Zen 4 does not simply turn the entire backend into a 512-bit machine.

A useful mental model, supported by AMD material and independent measurement, is:

- a 512-bit architectural vector operation can remain **one tracked macro/micro-operation through much of the front/middle of the core**;
- execution of many 512-bit arithmetic operations occurs on 256-bit hardware over two beats;
- the physical floating/vector register state is wide enough to track architectural ZMM values without splitting them into two independently scheduled frontend operations;
- some instructions have different internal decomposition, so this is not universal.

This can make ZMM code valuable even without doubling arithmetic throughput: one 512-bit instruction can reduce decode, dispatch, rename, and loop-control pressure relative to two 256-bit instructions.

But the data path may still be the bottleneck.

## 512-bit stores are special

Independent Zen 4 measurements show 512-bit stores consuming more backend resources than the simple one-tracked-op arithmetic model: they are handled as multiple pieces and can put disproportionate pressure on the 64-entry store queue.

For a packed low-precision representation, benchmark:

- compute in ZMM then store ZMM;
- compute in ZMM but narrow/store 256 or 128 bits;
- two YMM streams;
- four XMM streams.

Do not assume the fewest instructions wins.

# Load/store machinery

Zen 4 has three address-generation paths, but **address-generation opportunity, memory-operation issue count, and byte bandwidth are different quantities**.

AMD public material describes multiple loads/stores per cycle at the macro-operation level. Independent bandwidth measurements indicate the L1 data path is still organized around 256-bit transfers, commonly observed as approximately:

- two 32-byte load data paths per cycle;
- one 32-byte store data path per cycle.

A 512-bit load/store therefore interacts with a half-width physical data path even when the instruction remains compact elsewhere in the pipeline.

This distinction is especially important for E3M2/E4M3/E5M2/E5M3 work. Packing can reduce external bytes but increase:

- byte/word unpack operations;
- shuffles;
- sign/exponent extraction;
- widening;
- requantization;
- stores with awkward widths.

The useful unit is **total cycles per transformed stored value**, not floating-point operations per second.

## Load/store queues

Independent measurement reports:

- 64 store-queue entries;
- a larger ability to track loads than the published execution load-queue count suggests.

The store queue can become a real limiter in store-heavy AVX-512 code. For streaming transforms, collect PMU evidence for queue stalls rather than guessing from arithmetic utilization.

## Store-to-load forwarding and aliasing

Zen 4 can forward data from older stores to younger overlapping loads when its memory-disambiguation rules allow it.

When designing scratch layouts or in-place transforms, benchmark the exact store/load size and alignment combination. A mathematically trivial in-place update can be much slower than an equivalent register-resident update if forwarding or alias prediction behaves badly.

# Cache hierarchy

AMD's EPYC 9004 architecture material gives the common Zen 4 core hierarchy:

- 32 KiB, 8-way L1 instruction cache;
- 32 KiB, 8-way L1 data cache;
- 1 MiB private, unified L2 cache per core;
- 64-byte cache lines;
- on mainstream Genoa CCDs, up to eight cores sharing 32 MiB L3/LLC.

The exact EPYC 9V74 host topology behind this VM is not visible merely from the guest model string. The hypervisor can expose a synthetic topology and a subset of cache sharing.

## Latency and fill bandwidth

AMD's Zen 4 optimization material gives a roughly 4- or 5-cycle integer L1 data load-to-use latency depending on addressing/operation details.

AMD's current performance-counter tooling describes Zen 4 L2 fill bandwidth as 32 bytes/cycle for its derived bandwidth metrics.

L2/L3/DRAM effective latency and bandwidth in this VM must be measured because virtualization, vCPU placement, host NUMA, and neighboring workloads can dominate the architectural baseline.

## Working-set regimes

Every meaningful kernel benchmark should deliberately cross these regimes:

1. register-resident state;
2. L1-sized state;
3. private-L2-sized state;
4. LLC-sized state;
5. memory-sized state.

A representation can change rank between regimes. A decode-heavy compact format may lose in L1 and win in memory; a wide direct representation may do the opposite.

# Address translation

AMD's Zen 4 Software Optimization Guide documents:

- fully associative **64-entry L1 ITLB** for 4 KiB / 2 MiB / 1 GiB pages;
- fully associative **72-entry L1 DTLB** for 4 KiB / 16 KiB / 2 MiB / 1 GiB mappings;
- **512-entry, 8-way L2 ITLB** for 4 KiB and 2 MiB pages;
- **3072-entry, 24-way unified L2 DTLB** for 4 KiB / 16 KiB / 2 MiB mappings and page-directory entries;
- **six hardware page-table walkers**;
- a **64-entry page-directory cache** assisting walks.

The guide also documents opportunistic coalescing of suitable consecutive 4 KiB pages into effective 16 KiB translation entries in long mode.

For high-dimensional state much larger than cache, page layout may be part of performance. Measure 4 KiB pages versus huge pages if the environment permits it, and distinguish cache misses from TLB/page-walk stalls.

# Prefetch and memory access shape

Zen 4 has hardware data prefetch mechanisms for L1/L2 and instruction prefetching. Prefetchers are stateful and pattern-sensitive.

For transform layouts compare:

- contiguous structure-of-arrays;
- array-of-structures;
- fixed-stride planes;
- indexed/gather access;
- blocked/tiled layouts.

A "fewer arithmetic operations" layout that defeats the hardware prefetchers can lose to a seemingly wasteful contiguous layout.

Do not infer prefetch behavior from one warm run; include cold/warm and changing-stride tests.

# Current feature families: machine-level interpretation

The current guest's exposed extensions should be read as opportunities, not requirements.

### AVX2 / FMA

This is the mature 256-bit execution width that maps directly onto the physical vector datapaths. It is the baseline comparison for almost every wider-vector experiment.

### AVX-512 F/DQ/BW/VL

Adds ZMM width, mask registers, more register names, and richer element-width operations. On Zen 4 the front/middle-end benefits can exist even when execution is double-pumped on 256-bit arithmetic hardware.

### AVX-512 VNNI / BF16

These are particularly relevant to mixed-precision accumulated work. They do **not** directly implement E3M2/E4M3/E5M2/E5M3. Evaluate them as possible widened accumulation targets after storage decode.

### AVX-512 VBMI/VBMI2 / BITALG / VPOPCNTDQ

These can materially change the cost of packed-byte rearrangement and bitfield-heavy representations. Their value is representation-specific. Use instruction-specific uops.info data and a real end-to-end packed-format benchmark.

### IFMA

Useful for specific wide-integer/multiply-add representations, but not a general floating substitute.

### F16C

Provides conversion involving binary16 through older VEX-era instructions. It is not AVX-512 FP16 arithmetic, which this guest does not expose.

### AES / VAES / PCLMUL / VPCLMUL / SHA / GFNI

These are specialized data-path operations. They are worth knowing because some non-cryptographic bit/polynomial transformations can map to them, but such use must be justified by the actual operation rather than by cleverness.

### BMI1/BMI2 / ADX / POPCNT

Often useful for compact encodings, masks, bit extraction/deposition, carries, and counts. Again, instruction-specific costs and dependency chains matter.

### CLWB / CLFLUSHOPT / CLZERO

These concern cache-line state/persistence/zeroing and are not ordinary substitutes for stores. Use only when the memory-semantics requirement matches.

# PMU-guided optimization

AMD exposes performance-monitoring events capable of distinguishing important stall classes such as:

- operation-cache hit/miss and source of dispatched ops;
- frontend/op-queue starvation;
- FP scheduler pressure;
- FP physical-register pressure;
- integer physical-register pressure;
- load-queue pressure;
- store-queue pressure;
- taken-branch-buffer pressure;
- L2 demand/prefetch behavior;
- DTLB L2 hits/misses and page walks;
- retired instructions and unhalted cycles.

Whether KVM exposes all useful PMU events to this container must be checked before relying on them. If counters are unavailable, record that explicitly and fall back to timing plus controlled microbenchmarks rather than pretending an inferred bottleneck was measured.

# Performance questions to answer before a specialized lowering

Before choosing a Zen 4-specific representation or transform kernel, gather receipts for the exact VM and exact instruction sequence:

- dependency-chain latency;
- independent-instruction throughput;
- decode-source behavior for hot loops;
- 128/256/512-bit alternatives;
- register and mask-register pressure;
- integer versus vector scheduler pressure;
- aligned versus unaligned loads/stores;
- loads/stores crossing 64-byte cache-line boundaries;
- load-only, store-only, and mixed bandwidth;
- register/L1/L2/L3/DRAM working sets;
- shuffle/permute pressure;
- gather/scatter versus blocked contiguous access;
- conversion/widen/narrow cost for Float16/BF16/FP8-like storage;
- branch versus branchless/masked forms;
- 4 KiB versus huge-page behavior when available;
- cross-vCPU interference when the cloud scheduler changes placement.

For rotation work in particular, measure the primitive operation we actually want — for example **apply many independent small rotations to resident state** — rather than assuming GEMM or a BLAS call is the correct benchmark.

# Source hierarchy

Primary AMD sources:

- AMD uProf documentation, "Useful URLs", which links the official Zen 4 Software Optimization Guide, publication 57647:
  https://docs.amd.com/r/en-US/57368-uProf-user-guide/Useful-URLs
- official Zen 4 Software Optimization Guide ZIP:
  https://www.amd.com/content/dam/amd/en/documents/processor-tech-docs/software-optimization-guides/57647.zip
- AMD EPYC 9004 Architecture Overview, publication 58015:
  https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/white-papers/58015-epyc-9004-tg-architecture-overview.pdf
- AMD EPYC 9004 tuning material / processor identification:
  https://docs.amd.com/
- AMD Family 19h Models 10h-1Fh Revision Guide, publication 57095:
  https://docs.amd.com/v/u/en-US/57095-PUB_1.05
- AMD APML processor-identification/support notes:
  https://www.amd.com/en/developer/e-sms/apml-library.html

Compiler/measurement references:

- LLVM's Zen 4 scheduling model, annotated back to AMD SOG sections:
  https://github.com/llvm/llvm-project/blob/main/llvm/lib/Target/X86/X86ScheduleZnver4.td
- uops.info Zen 4 latency/throughput/port measurements:
  https://uops.info/
- Chips and Cheese, "AMD's Zen 4 Part 1: Frontend and Execution Engine":
  https://chipsandcheese.com/p/amds-zen-4-part-1-frontend-and-execution-engine
- Chips and Cheese, "AMD's Zen 4 Part 2: Memory Subsystem and Conclusion":
  https://chipsandcheese.com/p/amds-zen-4-part-2-memory-subsystem-and-conclusion

## Boundary

This note does not claim a new emitted backend surface, and it does not make AVX-512 a default. It records machine anatomy so target-specific work starts from the processor rather than from x86 extension names or historical library interfaces.
