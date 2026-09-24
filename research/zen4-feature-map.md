# Zen 4 current-container feature map

This file maps the **guest-visible instruction families** to the microarchitecture questions that matter before Idriç emits them deliberately.

It is not an ISA catalog. Exact encodings and semantics belong in the existing x86 ISA inventory. Exact instruction latency/throughput belongs in measured tables such as uops.info or a local receipt tied to this VM.

| Guest-visible family | Likely reason to care here | Zen 4 machine concern before using it |
| --- | --- | --- |
| SSE2/SSE4 | small scalar/packed baseline; narrow data | compare instruction count and partial-width dependencies against AVX forms |
| AVX | 256-bit FP state | VEX cleanup, 256-bit physical vector path |
| AVX2 | packed integer + FP ecosystem | strong baseline because physical arithmetic datapaths are 256-bit |
| FMA | rotation/linear-combination primitive | two 256-bit FMA-capable paths; measure dependency-chain vs independent issue |
| F16C | Float16 storage conversion | conversion only; widening/requantization cost can dominate tiny arithmetic |
| AVX512F | ZMM + masks + base arithmetic | 512-bit architectural state, commonly double-pumped arithmetic |
| AVX512DQ | wider integer/FP element operations | exact instruction routing varies; inspect individual costs |
| AVX512BW | byte/word vector operations | promising for compact formats; shuffles/conversions often dominate |
| AVX512VL | EVEX features on XMM/YMM | may gain masks/registers without paying full ZMM store cost |
| AVX512IFMA | integer fused multiply-add | specialized; useful only if representation math matches |
| AVX512CD | conflict detection | useful for irregular indexed work, not ordinary dense transforms |
| AVX512BF16 | BF16 dot/conversion/accumulation | candidate widening/accumulation waypoint, not FP8 arithmetic |
| AVX512VNNI | dot-product accumulation | strong for quantized integer accumulations; semantics must match |
| AVX512VBMI | byte permutes | potentially valuable for packed low-bit layouts; measure permutation bottleneck |
| AVX512VBMI2 | byte/word compress/expand/shift family | potentially useful for dense codec paths; instruction-specific costs |
| AVX512BITALG | bit algorithms | candidate for compact exponent/sign/mask manipulation |
| AVX512VPOPCNTDQ | vector population count | direct win only for count-heavy representations/algorithms |
| BMI1 | scalar bit manipulation | low-overhead scalar codec/control helpers |
| BMI2 | PEXT/PDEP/shift/multiply-related bit work | PEXT/PDEP costs are microarchitecture-specific; never assume "single instruction = cheap" |
| ADX | independent carry chains | useful for multiword integer arithmetic, not general FP |
| POPCNT | scalar bit counts | measure dependency and throughput if on critical path |
| AES/VAES | AES transforms | specialized; noncrypto reuse requires actual algebraic match |
| PCLMUL/VPCLMUL | carryless multiplication | useful for polynomial/GF(2) work; not ordinary multiply |
| SHA-NI | SHA assists | specialized fixed-function-ish path |
| GFNI | GF(2^8) affine/multiply operations | potentially powerful for byte codecs if the algebra matches |
| CLFLUSHOPT | cache-line flush | memory-state semantic operation, not a faster ordinary store |
| CLWB | cache-line writeback | persistence/cache-control semantics only |
| CLZERO | cache-line zeroing | useful only where zeroing semantics and availability fit |
| XSAVE family | architectural state save/restore | affects context-state footprint; not a compute primitive |

## Missing families that matter

The guest does **not** expose:

- AMX;
- AVX-512 FP16.

Therefore a design requiring AMX tile state or native AVX-512 FP16 arithmetic is not a design for this target.

## Selection rule

For each new target primitive:

1. state the mathematical/representation operation in ordinary words;
2. list plausible scalar, 128-bit, 256-bit, and 512-bit realizations;
3. consult AMD SOG and uops.info for candidate instructions;
4. benchmark the complete operation on this VM;
5. record cache working set, alignment, branch shape, and vCPU placement;
6. choose the lowering from measured end-to-end cost, not extension prestige.

This is especially important for compact low-precision formats, where unpack/repack and memory traffic may dominate the nominal arithmetic.
