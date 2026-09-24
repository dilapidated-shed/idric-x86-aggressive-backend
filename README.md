# Idriç generic AArch64 backend

This branch is the designated owner for direct generic A64 code generation. It is currently a scaffold: no executable backend is claimed yet.

Ownership boundaries:

- complete A64/NEON/SVE/SVE2/SME architecture inventory: `isomorphisms/idric-big-iron:arch/aarch64-sve`;
- direct generic A64 instruction selection and emitted/tested support: this branch;
- original-Switch target mask and platform/runtime: `isomorphisms/idric-embedded:switch`;
- Apple ABI/Mach-O/SoC profiles: this repository's `Apple` branch;
- GPU/shader work: `isomorphisms/idris-shader-backend`.

The backend follows accepted `Idric` semantics and ARM/Thumb-proven compiler seams, fixtures, oracles, rejection boundaries, and verification structure. It uses target-native A64 instructions and ABI rules rather than imitating Thumb encodings or tricks.

RefC/C is not a fallback. The first milestone is one direct `.idric` program lowered to an inspectable A64 object/executable with an exact execution oracle.

Tracking issue: [#8](https://github.com/isomorphisms/idric-x86-aggressive-backend/issues/8).

Concrete Allwinner A333 / sun65iw1p1 processor notes and the physical-measurement checklist live in [`MICROARCHITECTURE.md`](MICROARCHITECTURE.md). Keep SoC facts separate from generic A64 configuration possibilities.
