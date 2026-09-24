# Machine convolution type

Status: exploratory note. This is not yet a compiler ABI or storage-format commitment.

## Idea

Treat convolution as a first-class machine/compiler type rather than starting from
"ternary digits packed into binary."

The motivating exact kernel is

```text
[1, 1, 1]
```

with the recurrence

```text
next[i] = prev[i - 1] + prev[i] + prev[i + 1]
```

starting from the impulse `[1]`.

The first rows are

```text
1
1 1 1
1 2 3 2 1
1 3 6 7 6 3 1
1 4 10 16 19 16 10 4 1
```

These are coefficients of `(x^-1 + 1 + x)^n`, equivalently shifted
coefficients of `(1 + x + x^2)^n`.  The row sum is exactly `3^n`.

So an exact probability row can be represented as

```text
integer coefficients + step n
```

with denominator `3^n` implicit.  No floating-point representation is needed.

## Why make it a type?

The type should describe the mathematical operation and its invariants, not one
permanent bit layout.

Possible information carried by the type:

- coefficient domain;
- fixed kernel;
- support/radius;
- convolution step/count;
- exact overflow bound or widening rule;
- symmetry, when proven;
- normalization base, here `3`.

A sketch, not syntax:

```text
MachineConvolution coefficient kernel step
```

For the trinomial/Gaussian experiment, `kernel = [1,1,1]`.  A compiler can
then lower the same type to scalar integer code, SIMD, a special accelerator,
or some future redundant arithmetic representation without changing its
mathematical meaning.

## This is operation-centered, not ternary storage

Balanced ternary storage asks how to encode digits in `{-1,0,+1}`.

This experiment asks how to retain and execute the exact convolution generated
by those three choices.  Repeated addition produces a discrete bell-shaped
distribution automatically.  The machine object is the convolution state, not
a packed ternary numeral.

That distinction matters: packing density is secondary.  We can deliberately
use wider temporary states, delayed normalization, or redundant arithmetic if
they make the operation cheaper.

## Invariants for a first acceptance slice

For step `n`:

1. support is `[-n,n]`;
2. coefficients are nonnegative integers;
3. the row is symmetric;
4. the coefficient sum is exactly `3^n`;
5. one step is exactly convolution by `[1,1,1]`;
6. no Float16/32/64 is used in the exact path;
7. overflow is explicit: widen, reject, or use an arbitrary-precision reference.

Acceptance should compare emitted target code against an exact reference for a
small sequence of rows and inspect the generated machine instructions.

## Prior art / novelty caution

None of the individual pieces is new:

- trinomial coefficients and the three-parent Pascal-style recurrence are old;
- DSP and ML implementations perform convolution constantly;
- SIMD and convolution accelerators specialize the operation;
- redundant signed-digit arithmetic has been used to reduce carry propagation;
- recent accelerator work has even combined redundant signed-digit arithmetic
  with convolution windows.

The exploratory point here is narrower: make an exact convolution object with
its algebraic invariants a first-class compiler/machine type, then let each
backend choose the representation and lowering.  Do not claim novelty without
a dedicated literature search.

Related directions to inspect:

- central/trinomial coefficients and `(1+x+x^2)^n`;
- Avizienis-style redundant signed-digit arithmetic;
- carry-save / borrow-save intermediate forms;
- SIMD FIR/direct-convolution kernels;
- systolic/tensor convolution hardware;
- block-valued compiler IRs.

## First question

Does preserving convolution as a typed operation expose optimizations that are
lost when the frontend immediately expands it into unrelated scalar adds,
loads, and stores?

That is the experiment.


## x86-64 notes

Start with the existing direct-ELF64 integer path.  Keep the semantic type
independent of SSE/AVX width.

Useful experiments:

- scalar three-neighbor recurrence as the correctness baseline;
- SSE2/AVX2/AVX-512 lane-wise integer additions on the corresponding target
  branches;
- shifted/overlapping loads versus register shuffles for the three neighbors;
- widening before overflow;
- exploit symmetry only when doing so actually reduces total loads/stores;
- compare immediate normalization against delayed/redundant accumulation.

The interesting result is not merely "SIMD convolution is fast"; that is
already established.  The question is whether retaining convolution in the IR
long enough lets the backend choose a materially better lowering than scalar
operation-by-operation code.
