# Zen 4 microarchitecture and the current x86 execution target

Status: research and target evidence. This document is deliberately separate from the x86 ISA inventory. An instruction being architecturally available does not say how this processor schedules, executes, caches, or feeds it.

## Evidence levels

Keep these levels separate when making optimization decisions:

1. **Observed target contract** — what the current KVM guest actually exposes through Linux and CPUID-derived flags.
2. **AMD processor documentation** — facts about the relevant Family 19h / Zen 4 / EPYC 9004 implementation family.
3. **Measured microarchitecture** — latency, throughput, and execution-resource measurements from independent microbenchmarks such as uops.info.
4. **Analytical reverse engineering** — useful explanations from sources such as Chips and Cheese, but not an AMD architectural promise.

Do not promote levels 3 or 4 into an ISA guarantee. Do not infer physical host topology from a virtual machine's lscpu topology.

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

The cache-instance counts and the 5-core/1-thread topology are a **guest presentation**, not evidence for the host package topology. The model/family/stepping and exposed instruction flags are the useful compilation contract; physical contention and cache-sharing still require measurements in the running VM.

AMD's APML documentation explicitly names Family 19h Model 11h B1, and AMD classifies Family 19h Models 10h-1Fh as Zen 4 / EPYC 9004-family processors.

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

This list is a target mask, not a statement that every instruction has attractive throughput.

## Zen 4 cache and package structure relevant to this target family

AMD's EPYC 9004 architecture overview gives the following Zen 4 core baseline:

- up to 32 KiB 8-way L1 instruction cache per core;
- up to 32 KiB 8-way L1 data cache per core;
- up to 1 MiB private unified L2 per core;
- SMT2 capability in the physical core;
- for mainstream 91xx-96xx EPYC 9004 parts, up to eight Zen 4 cores share an L3/LLC in a CCX, and a CCD contains one such CCX;
- AMD separately documents 32 MiB L3 per CCD for that family.

The VM may expose only a slice of those resources and may hide SMT. Optimize the actual guest only after measuring its effective cache and bandwidth behavior.

## Wide-vector execution: do not equate width with throughput

The most important warning for micro-optimized work is that AVX-512 support does **not** mean a 512-bit-wide backend for every operation.

Independent Zen 4 measurements and reverse engineering show a characteristic pattern:

- many 512-bit vector instructions remain a single tracked operation through much of the out-of-order machinery;
- arithmetic is commonly executed by 256-bit machinery in two halves ("double pumped");
- 512-bit stores are more expensive in backend resources than a simple one-operation mental model suggests;
- instruction-specific throughput varies substantially even within one ISA family.

For example, uops.info measures Zen 4 instruction throughput and port/resource use instruction by instruction. Use those measurements rather than a blanket rule such as "ZMM is twice YMM."

The consequence for Idriç lowering is simple: vector width, register pressure, load/store traffic, and instruction count must be considered together. A 512-bit encoding can still be worthwhile because it reduces front-end and rename pressure even when arithmetic throughput is not doubled.

## Performance questions to answer before a specialized lowering

Before choosing a Zen 4-specific representation or transform kernel, gather receipts for the exact VM and exact instruction sequence:

- dependency-chain latency;
- independent-instruction throughput;
- 128/256/512-bit alternatives;
- aligned versus unaligned loads/stores;
- load-only, store-only, and mixed bandwidth;
- cache-resident versus L2/L3/DRAM working sets;
- shuffle/permute pressure;
- mask-register pressure;
- conversion/widen/narrow cost for Float16/BF16/FP8-like storage;
- branch versus branchless forms;
- cross-vCPU interference when the cloud scheduler changes placement.

For rotation work in particular, measure the primitive operation we actually want — for example "apply many independent small rotations to resident state" — rather than assuming GEMM or a BLAS call is the correct benchmark.

## Source hierarchy

Primary AMD sources:

- AMD uProf documentation, "Useful URLs", which links the Zen 4 Software Optimization Guide, publication 57647:
  https://docs.amd.com/r/en-US/57368-uProf-user-guide/Useful-URLs
- AMD EPYC 9004 Architecture Overview, publication 58015:
  https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/white-papers/58015-epyc-9004-tg-architecture-overview.pdf
- AMD Family 19h Models 10h-1Fh Revision Guide, publication 57095:
  https://docs.amd.com/v/u/en-US/57095-PUB_1.05
- AMD APML library processor-identification/support notes:
  https://www.amd.com/en/developer/e-sms/apml-library.html

Measured/secondary sources:

- uops.info Zen 4 latency/throughput/port measurements:
  https://uops.info/
- Chips and Cheese, "AMD's Zen 4 Part 1: Frontend and Execution Engine":
  https://old.chipsandcheese.com/2022/11/05/amds-zen-4-part-1-frontend-and-execution-engine/

## Boundary

This note does not claim a new emitted backend surface, and it does not make AVX-512 a default. It records enough machine anatomy to prevent optimization work from being designed against x86 ISA names alone.
