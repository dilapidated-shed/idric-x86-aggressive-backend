# Source notes: redundant arithmetic and direct convolution

These notes record the two sources linked in the machine-convolution discussion.
They are background evidence, not evidence that the proposed
`MachineConvolution` compiler type is novel.

## ScienceDirect: modified signed-digit recoding

**Citation**

A.K. Cherri et al. / *Recoding algorithms for the modified signed-digit
numbers for parallel digital computing*, Computers & Electrical Engineering,
24(5), 1998, pp. 279–294.

DOI: 10.1016/S0045-7906(98)00009-3

URL:

```text
https://www.sciencedirect.com/science/article/abs/pii/S0045790698000093
```

### What it actually establishes

The paper is about modified signed-digit (MSD) arithmetic with radix 2 and
digit set `{-1, 0, +1}`.  Its motivation is parallel arithmetic with limited
carry and borrow propagation.  It develops recoding algorithms intended to
support carry-free arithmetic and discusses multi-bit parallel circuit
realizations.

This is directly relevant to our question about spending representational
redundancy to reduce inter-digit dependency.

### Important correction

This exact ScienceDirect link is **not** a paper about convolution windows.
Earlier discussion accidentally described it too broadly.  It supports the
redundant-signed-digit / carry-propagation side of the idea, not the
convolution-specific side.

A separate, newer line of work does combine signed-digit/online arithmetic
with convolution accelerators.  Keep that as a distinct source if we decide
to survey it; do not attribute it to the 1998 paper.

### Questions to carry into the backend experiment

- Which redundant encoding is assumed?
- How many neighboring digit positions can a carry/borrow affect?
- Is the benefit still present when implemented as ordinary ARM/x86
  instructions rather than custom logic?
- Does a compiler-level convolution object provide enough structure to choose
  a redundant intermediate representation profitably?
- Where is normalization best delayed, and what exact widening bound is needed?

## Google Patents: EP3676700B1

**Title:** *Efficient direct convolution using SIMD instructions*

**Inventors:** Jeffrey R. Diamond; Avadh P. Patel

**Assignee listed by Google Patents:** Oracle International Corp.

**Priority:** 2017-09-08

**EP grant publication:** 2022-12-28

URL:

```text
https://patents.google.com/patent/EP3676700B1/en
```

### Relevant technical idea

The patent discusses performing direct convolution on general-purpose SIMD
hardware without first lowering the whole convolution to GEMM or transforming
it into the frequency domain.

The useful implementation pattern for us is:

1. load a source vector aligned with the destination vector;
2. obtain neighboring/shifted source vectors covering the left and right
   partial data needed by the convolution window;
3. multiply those vectors by the corresponding convolution coefficients;
4. accumulate into one or more destination vectors;
5. write the accumulated result after the required source vectors have been
   processed.

It also discusses using vector extract/shift operations to construct unaligned
neighbor vectors from aligned source vectors, and reusing loaded source vectors
across multiple accumulators.

### Why it matters to MachineConvolution

This is evidence for a backend-level point: preserving the convolution
operation long enough can expose data reuse, shifted-neighbor construction, and
multiple-accumulator SIMD strategies that are harder to recover after an early
scalar expansion.

For the exact `[1,1,1]` kernel, multiplication by coefficients disappears.
The interesting lowering becomes even simpler:

```text
left + center + right
```

over multiple lanes, with attention to how neighboring lanes/blocks are
constructed and reused.

### What it does not establish

- It does not establish the proposed compiler type.
- It does not establish redundant signed-digit arithmetic.
- It does not establish that a particular ARMv7-A or x86-64 lowering will win.
- A patent is useful technical prior-art evidence, not a benchmark result.
- Patent status/legal scope is separate from the engineering question; do not
  infer freedom-to-operate from these notes.

## Combined lesson

The two sources support different halves of the experiment:

```text
1998 MSD paper
    redundancy -> reduced carry/borrow propagation

EP3676700B1
    preserved convolution structure -> SIMD neighbor reuse
```

Our experiment is to see whether a first-class exact convolution type lets a
backend exploit either or both:

```text
exact convolution semantics
        |
        +-- conventional scalar/SIMD lowering
        |
        +-- delayed normalization / redundant intermediate arithmetic
```

Keep those claims separate until measurements connect them.
