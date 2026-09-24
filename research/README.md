# x86 ISA and microarchitecture research inputs

The ISA inventory and the microarchitecture notes are separate evidence layers.

- `source-pins.json` records the exact machine-readable and architectural references used for the ISA inventory.
- `vendor-differences.tsv` records manually checked Intel/AMD ISA-semantic differences.
- `zen4-microarchitecture.md` records the current KVM target profile plus Zen 4 frontend, out-of-order, integer, vector, load/store, cache, TLB, branch, SMT, and PMU facts.
- `zen4-feature-map.md` maps every important guest-exposed extension family to the machine-level question that must be answered before using it.\n- `container-target-20260924.md` retains the exact guest identity, full Linux feature-flag line, cache sysfs geometry, virtualization inconsistency, and kernel-reported speculation state used for this research pass.

The generated instruction inventory is intentionally reproducible: changing a source revision is an explicit repository change, not an unnoticed consequence of running against whatever XED happens to be current that day.

Microarchitecture evidence must not be generalized into an ISA guarantee. In particular, guest-visible topology is not physical-host topology, and instruction availability does not imply useful throughput.
