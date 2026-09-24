# Allwinner A333 tablet microarchitecture

Status: concrete-target research for the A333 / sun65iw1p1 Android AArch64 target. This document is intentionally separate from the generic A64 ISA catalog in `isomorphisms/idric-big-iron:arch/aarch64-sve`.

The point of this file is to prevent a generic Arm model from silently standing in for the actual heterogeneous tablet SoC.

## Evidence boundary

Keep four layers separate:

1. **A333 silicon facts** published by Allwinner.
2. **Arm core/GPU implementation facts** for Cortex-A73, Cortex-A53, and Valhall/Mali-G57.
3. **Configuration ranges** licensed by Arm to silicon vendors.
4. **Observed facts from the physical tablet**.

A legal Cortex-A73 or Cortex-A53 cache configuration is not evidence that Allwinner chose it. A generic Mali-G57 capability is not proof of the A333's system cache or DRAM bandwidth. Fill those fields only from A333 documentation or physical observation.

## A333 top-level organization

Allwinner's current A333 documentation identifies the relevant part as a five-core big.LITTLE tablet SoC:

- 1 × Arm Cortex-A73;
- 4 × Arm Cortex-A53;
- maximum CPU frequency up to 1.8 GHz for the documented A333MX-0XX part;
- Arm Mali-G57 **MC1** GPU;
- XuanTie E902 RISC-V coprocessor;
- 32-bit external memory interface, up to 8 GB;
- DDR3/DDR3L/LPDDR3 and DDR4/LPDDR4/LPDDR4x support;
- PCIe 2.1, USB 3.1 Gen1 DRD, GMAC, and other tablet/display interfaces.

Allwinner explicitly warns that the A333 family has multiple submodels and that its product page describes A333MX-0XX. Do not infer that every A333 tablet has identical clocks, DRAM, or peripheral configuration.

The SoC is also known in Linux/board-support material as the sun65i family; the physical target's hardware string `sun65iw1p1` belongs in target receipts, but that string alone does not establish every cache/interconnect parameter.

## CPU asymmetry is fundamental

This is not a five-way symmetric CPU.

### Cortex-A73 big core

Arm's Cortex-A73 TRM describes:

- a superscalar, variable-length, out-of-order pipeline;
- sustained maximum throughput of two instructions per cycle;
- private L1 memory systems per core;
- a shared L2 cache at the Cortex-A73 cluster level in the generic IP;
- up to four A73 cores per generic cluster, although A333 implements only one.

Arm's Cortex-A73 launch material describes the core as having:

- a 64 KiB instruction-cache option in the promoted mobile configuration;
- advanced branch prediction and instruction prefetch;
- advanced L1/L2 data prefetch;
- an optimized store buffer for streaming writes;
- a data-cache option up to 64 KiB.

Arm's comparison table gives the wider configurable envelope as 32 KiB I-cache, 32–64 KiB D-cache, and 256 KiB–8 MiB shared L2 for Cortex-A73 implementations.

**Do not put those configurable sizes into an A333 performance model until the physical tablet or an Allwinner source establishes the chosen configuration.**

### Cortex-A53 efficiency cores

Arm describes Cortex-A53 as:

- an 8-stage in-order pipeline;
- substantially/full dual-issue relative to earlier efficiency cores;
- improved floating-point/SIMD throughput and internal buses;
- a low-latency integrated L2 design;
- a 512-entry main TLB;
- sophisticated branch prediction for an in-order efficiency core.

The generic Cortex-A53 IP permits multiple L1/L2 cache configurations. Again, these are legal configuration ranges, not A333 cache facts.

### Scheduling consequence

Any CPU microbenchmark must state which class of core executed it.

At minimum, benchmark separately:

- the single A73;
- one A53;
- multiple A53s;
- A73 + A53 concurrent work.

Do not report an average over all five CPUs as if it described one core. Android's scheduler, DVFS, thermal policy, and foreground/background state can move work between the A73 and A53s unless affinity is controlled or observed.

For tiny-float decode/compute/encode and small-rotation work, measure both cores. An instruction sequence that wins on the out-of-order A73 can lose on the in-order A53 because dependency depth, load latency hiding, and register pressure have different costs.

## NEON / floating-point boundary

Both Cortex-A73 and Cortex-A53 are Armv8-A application cores with Advanced SIMD/NEON capability, but do not infer a server-style SVE machine from the generic A64 backend.

The tablet target should treat 128-bit NEON as the relevant SIMD family unless the physical target proves additional architectural features.

For compact-number experiments, record separately:

- scalar integer unpack/pack;
- NEON integer unpack/pack;
- FP16 support actually exposed by HWCAP/CPU feature registers;
- widening to FP32 and requantization;
- permutation/shuffle cost;
- aligned and unaligned packed access;
- dependency-chain versus independent-operation throughput.

## Mali-G57 MC1: one Valhall shader core

Allwinner specifies **Mali-G57 MC1**. MC1 means the SoC integrates one Mali-G57 shader core; do not mentally substitute a multi-core G57 benchmark.

Mali-G57 belongs to Arm's Valhall architecture. Arm's Valhall shader-core guide describes the relevant execution model:

- 16-wide warps;
- dynamic hardware scheduling;
- two parallel processing engines inside a shader core;
- per processing engine: FMA, CVT, and special-function arithmetic pipelines;
- 16-wide FMA and CVT datapaths;
- a narrower special-function path;
- register use directly affects the number of resident threads/warps;
- fp16/int16 and int8 packed arithmetic can increase arithmetic density compared with fp32.

Arm's published Mali data gives Mali-G57 twice the nominal FP16 operations/clock of FP32 for appropriate arithmetic.

That makes this GPU interesting for low-precision work even though it is only MC1. The important questions are whether a candidate representation:

- stays in registers;
- uses packed 16-bit arithmetic effectively;
- avoids spills;
- avoids excessive conversion/shuffle instructions;
- exposes enough independent work for the hardware scheduler;
- avoids CPU/GPU memory traffic becoming the limiting resource.

### GPU configuration facts we do not yet have

The generic Valhall IP does not establish these A333-specific facts:

- GPU clock/frequency table;
- GPU-side L2/system-cache size;
- exact memory-controller bandwidth;
- arbitration between CPU, GPU, video, and display clients;
- driver scheduling behavior;
- Mali driver revision and exposed Vulkan/OpenCL extensions;
- performance-counter access from the Android build.

Leave them unknown until read from the physical target or authoritative Allwinner/driver documentation.

## Shared memory system

Allwinner documents a 32-bit external memory interface and support for several DDR/LPDDR generations. It does **not** prove which memory technology and speed the physical tablet uses.

Because CPU and GPU ultimately share system memory, compact formats can matter twice:

1. fewer bytes moved;
2. potentially more unpack/convert work.

That trade must be measured on this exact device. A representation that is arithmetic-expensive but bandwidth-cheap can behave differently on A73, A53, and Mali-G57.

## Thermal and frequency behavior

This is a fanless tablet-class target. A one-second benchmark and a sustained kernel are different workloads.

Every serious performance receipt should record or sample:

- CPU frequency policy and actual frequency;
- which CPU class ran the work;
- thermal-zone temperatures;
- throttling/frequency changes during the run;
- GPU frequency when observable;
- battery/charging state when it affects governor behavior.

A result obtained before thermal equilibrium must not be treated as sustained throughput.

## Physical-target inventory to collect before hand optimization

Read-only probes should establish, where Android exposes them:

- `/proc/cpuinfo` implementer/part/revision per CPU;
- online CPUs and capacity/frequency classes;
- `/sys/devices/system/cpu/cpu*/cache/` cache sizes, associativity, line size, sharing;
- cpufreq policies, governors, available/current frequencies;
- HWCAP/HWCAP2 and Android CPU-feature exposure;
- device-tree or kernel-visible SoC/interconnect/memory-controller identifiers;
- total memory and, if discoverable without guesswork, DRAM type/rate;
- page size and TLB-relevant kernel configuration;
- PMU/perf counter accessibility;
- Mali kernel/Android driver version;
- Vulkan device properties and extensions;
- Mali performance-counter access if available.

Then measure:

- A73 and A53 scalar latency/throughput separately;
- NEON integer/FP32/FP16 operations actually relevant to our compact formats;
- loads/stores at L1/L2/DRAM-sized working sets;
- packed byte/halfword load, unpack, shuffle, conversion, and repack paths;
- A73/A53 concurrent memory pressure;
- GPU arithmetic and memory kernels;
- CPU + GPU contention;
- sustained thermal-state performance.

## Sources

Allwinner:

- A333 product page:
  https://www.allwinnertech.com/index.php?a=index&c=product&id=137
- A333 product brief:
  https://www.allwinnertech.com/uploads/download_source/20260303162657a4.pdf

Arm CPU:

- Cortex-A73 Technical Reference Manual:
  https://documentation-service.arm.com/static/5e7b6c837158f500bd5c03fc
- Cortex-A73 launch/microarchitecture notes:
  https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/new-arm-cortex-a73-processor-drives-efficiency-performance-for-mobile-designs
- Cortex-A53 microarchitecture overview:
  https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/the-top-5-things-to-know-about-cortex-a53
- Cortex-A processor comparison table:
  https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Cortex-A%20R%20M%20datasheets/Arm%20Cortex-A%20Comparison%20Table_v4.pdf

Arm GPU:

- Valhall Shader Core User Guide:
  https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/The%20Valhall%20Shader%20Core.pdf
- Valhall / Mali-G77 architecture overview:
  https://developer.arm.com/community/arm-community-blogs/b/mobile-graphics-and-gaming-blog/posts/introducing-arm-mali-g77-with-new-valhall-architecture
- Mali FP16/FP32 arithmetic-rate comparison:
  https://developer.arm.com/community/arm-community-blogs/b/ai-blog/posts/making-the-most-of-arm-nn-for-gpu-inference

## Boundary

This document records known machine structure and missing measurements. It does not claim that the generic A64 backend is executable yet, and it does not invent A333 cache sizes, memory speed, or GPU cache configuration from the legal configuration ranges of the licensed Arm cores.
