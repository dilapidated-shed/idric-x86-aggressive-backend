# x86-64 complex/projective leading implementation

For complex and projective arithmetic only, this branch is the executable Float32 implementation line. This does not redefine mathematical complex numbers: Idriç keeps the complex carrier parametric, while this backend lowers one concrete Float32 carrier to two scalar machine components.

## Semantic boundary

The canonical structural contract is the current Idriç complex/projective branch and its shared corpus:

```text
_/fixtures/complex-projective/float32.json
```

The x86 acceptance path validates the corpus discriminators before generation. It rejects unsupported schema, precision/rounding, comparison modes, exponential implementation/degree/radius, render field, coloring identifier, and cross-backend pixel-equality policy instead of silently applying hard-coded semantics.

Projective values remain homogeneous complex coordinates. Equality is never raw component equality: supplied equivalence fixtures use their explicit common nonzero rescaling witnesses, while non-equivalence uses invariant residuals `zi*wj - zj*wi`. The corpus `expected_equivalent` value is authoritative and is checked against the executed residual.

## Direct candidates

Python constructs instruction bytes and the backend-owned ELF64 envelope. Candidate arithmetic does not pass through C, an assembler, linker, libc, libm, RefC, LLVM, or another host backend.

The acceptance run generates three direct ELF64 programs:

- `complex-corpus.elf` executes the Float32 arithmetic, supplied projective rescaling residuals, invariant non-equivalence residual, bounded exponential, polar observation, and the older embedded-representative chart extraction;
- `complex-projective-contract.elf` executes the missing CP¹ contract explicitly;
- `complex-render.elf` executes the deterministic renderer.

The CP¹ contract candidate performs

```text
z
-> [1:z]
-> first chart
-> z
```

from the corpus `affine` value. It retains the constructed `[1:z]` coordinates in candidate state, computes an executable residual against the corpus `embedded` representative, then extracts the first chart from that constructed representative.

For the corpus `[0:1]` fixture, the same candidate tests the first homogeneous coordinate and emits an explicit `first_chart_defined` result. It does not divide the infinity representative and does not interpret NaN or infinity as chart undefined.

## Bounded exponential

The implementation remains the degree-7 complex Taylor polynomial and is accepted only for `|q| <= 0.5`. A standalone exponential input beyond that radius is rejected. A render is rejected if any sampled `q(z)` leaves that radius.

The receipt records the error evidence separately:

```text
exp_truncation_bound
    = exp(|q|) |q|^8 / 8!

exp_float32_rounding_allowance
    = 64 * epsilon * exp(|q|)

exp_total_bound
    = exp_truncation_bound + exp_float32_rounding_allowance
```

The factor 64 is an implementation-specific conservative Float32 allowance in this x86 lane; it is not part of the carrier-neutral Idriç semantics.

## Renderer

`complex-render.elf` directly computes a deterministic binary PPM from

```text
z
-> q(z)
-> bounded exp(q(z))
-> R(z) from the explicit zero/pole divisor
-> f(z) = R(z) exp(q(z))
-> observation/coloring
```

The generated instruction path computes `q`, stores `exp(q)`, constructs `R` only from zero and pole factors, multiplies them to obtain `f`, and only then computes magnitude and RGB observations. Magnitude, phase, conjugation, or coloring do not feed back into `q`, `exp(q)`, `R`, or `f`.

The x86 lane requires deterministic same-backend regeneration. The corpus explicitly does not require cross-backend pixel equality.

## Evidence

The GitHub-hosted job runs on Ubuntu x86-64 and checks out the exact PR head rather than the synthetic pull-request merge ref. It records the exact backend head, exact Idriç semantic/corpus SHA, corpus SHA-256, every generated ELF SHA-256, the numerical output hashes, the three exponential bounds, and the render SHA-256.

The generated ELFs are executed directly on that Ubuntu host. Ubuntu execution is the maintained Linux acceptance boundary. Historical Debian receipts may remain as historical evidence, but Debian is not an additional required runtime or acceptance gate.

The final receipt keeps detailed executed stages for:

- complex arithmetic;
- explicit projective rescaling;
- invariant projective non-equivalence;
- affine embedding;
- finite first-chart extraction;
- CP¹ infinity / undefined first chart;
- bounded complex exponential;
- deterministic `R(z) exp(q(z))` render;
- semantic discriminator rejection.

The current ai-ci v1 policy requires aggregate `native_execution`, `numerical_corpus`, `projective_corpus`, and `headless_render` stage names. Those aggregate entries are emitted only after the detailed subcases have passed; they are not substitutes for the detailed evidence.
