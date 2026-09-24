# Current x86 container target receipt — 2026-09-24

This is a literal read-only machine snapshot used to bind the Zen 4 research notes to the execution environment that was actually available on 2026-09-24.

It is **guest evidence**. KVM may synthesize CPU topology, cache-sharing relationships, vulnerability exposure, and CPUID features. Do not treat this as a physical-host inventory.

## uname

```text
Linux 1b4b415cd501 6.18.44 #1 SMP Tue Sep 22 17:26:16 UTC 2026 x86_64 GNU/Linux
```

## lscpu identity/topology

```text
Architecture:        x86_64
CPU op-mode(s):      32-bit, 64-bit
Address sizes:       46 bits physical, 48 bits virtual
Byte Order:          Little Endian
CPU(s):              5
On-line CPU(s):      0-4
Vendor ID:           AuthenticAMD
Model name:          AMD EPYC 9V74 80-Core Processor
CPU family:          25
Model:               17
Thread(s) per core:  1
Core(s) per socket:  5
Socket(s):           1
Stepping:            1
Hypervisor vendor:   KVM
Virtualization type: full
NUMA node(s):        1
NUMA node0 CPU(s):   0-4
```

## Exact Linux CPU flags

```text
fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush
mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc
rep_good nopl xtopology nonstop_tsc cpuid extd_apicid tsc_known_freq pni
pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt
tsc_deadline_timer aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy
cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext vmmcall fsgsbase
tsc_adjust bmi1 avx2 smep bmi2 erms invpcid avx512f avx512dq rdseed adx smap
avx512ifma clflushopt clwb avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec
xgetbv1 xsaves avx512_bf16 clzero xsaveerptr arat npt nrip_save tsc_scale
vmcb_clean flushbyasid pausefilter pfthreshold v_vmsave_vmload avx512vbmi umip
avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg
avx512_vpopcntdq rdpid fsrm arch_capabilities
```

The flags are copied exactly from the first `flags` line in `/proc/cpuinfo`, only wrapped for readability. No missing feature should be inferred from this file without checking how Linux names or suppresses that CPUID feature.

## Guest cache summary

```text
L1d cache: 96 KiB (3 instances)
L1i cache: 96 KiB (3 instances)
L2 cache:  3 MiB (3 instances)
L3 cache:  32 MiB (1 instance)
```

## CPU0 cache sysfs

```text
index0
  level=1
  type=Data
  size=32K
  coherency_line_size=64
  ways_of_associativity=8
  number_of_sets=64
  shared_cpu_list=0-1

index1
  level=1
  type=Instruction
  size=32K
  coherency_line_size=64
  ways_of_associativity=8
  number_of_sets=64
  shared_cpu_list=0-1

index2
  level=2
  type=Unified
  size=1024K
  coherency_line_size=64
  ways_of_associativity=8
  number_of_sets=2048
  shared_cpu_list=0-1

index3
  level=3
  type=Unified
  size=32768K
  coherency_line_size=64
  ways_of_associativity=16
  number_of_sets=32768
  shared_cpu_list=0-4
```

The guest says `Thread(s) per core: 1` while CPU0's private-cache sysfs entries say `shared_cpu_list=0-1`. That mismatch is itself evidence that the topology is virtualized/synthetic. Do not use the sharing lists as proof of physical SMT/core placement.

## Kernel-reported speculation/security exposure

This is not part of the compiler's ordinary feature mask, but it can alter timing and is retained because the target is a VM:

```text
gather_data_sampling: Not affected
ghostwrite: Not affected
indirect_target_selection: Not affected
itlb_multihit: Not affected
l1tf: Not affected
mds: Not affected
meltdown: Not affected
mmio_stale_data: Not affected
old_microcode: Not affected
reg_file_data_sampling: Not affected
retbleed: Not affected
spec_rstack_overflow: Vulnerable
spec_store_bypass: Vulnerable
spectre_v1: Vulnerable: __user pointer sanitization and usercopy barriers only; no swapgs barriers
spectre_v2: Vulnerable; STIBP: disabled; PBRSB-eIBRS: Not affected; BHI: Not affected
srbds: Not affected
tsa: Vulnerable
tsx_async_abort: Not affected
vmscape: Not affected
```

A later run may differ after host/kernel/microcode or VM configuration changes. Performance receipts should therefore retain their own date and kernel/CPUID identity instead of silently inheriting this snapshot.
