"""Narrow executable bridge from the Idriç Float32 corpus to x86-64 acceptance."""

from __future__ import annotations

import math
from typing import Any

from backend.complex_projective import (
    F32_EPSILON,
    X86,
    _complex_divide,
    _complex_multiply,
    _load_complex,
    _load_complex_rhs,
    _register_complex,
    _store_result,
)
from backend.elf64 import write_elf

CORPUS_SCHEMA = "idric-complex-projective-corpus-v1"
PRECISION_NAME = "Float32"
PRECISION_ROUNDING = "round-to-nearest-even at stored binary32 operation boundaries"
EXPONENTIAL_KIND = "complex-taylor"
EXPONENTIAL_DEGREE = 7
EXPONENTIAL_MAXIMUM_INPUT_MAGNITUDE = 0.5
RENDER_FIELD = "f(z)=R(z)*exp(q(z))"
RENDER_COLORING = "phase-sensitive-rgb-v1"

COMPARISON_MODES = {
    "add": "exact-binary32",
    "multiply": "exact-binary32",
    "reciprocal": "floating",
    "divide": "floating",
    "conjugate": "exact-binary32",
    "magnitude_squared": "exact-binary32",
    "power_two": "exact-binary32",
    "polynomial": "exact-binary32",
    "rational": "floating",
    "exponential": "bounded-analytic-approximation",
    "polar_round_trip": "floating",
}

PROJECTIVE_CASES = {
    "equivalent_real_scale_cp2",
    "equivalent_phase_scale_cp2",
    "non_equivalent_cp2",
    "affine_chart_cp1",
    "infinity_cp1",
}


def _require_exact_keys(mapping: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(mapping)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{label} keys do not match supported corpus contract; "
            f"missing={missing}, unknown={unknown}"
        )


def _require_complex_pair(value: Any, label: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(component, (int, float)) for component in value)
    ):
        raise ValueError(f"{label} must be one [real, imaginary] pair")


def validate_corpus_contract(corpus: dict[str, Any]) -> None:
    """Reject semantic discriminator changes that this backend does not implement."""
    if corpus.get("schema") != CORPUS_SCHEMA:
        raise ValueError("unsupported complex/projective corpus schema")

    precision = corpus.get("precision")
    if not isinstance(precision, dict):
        raise ValueError("missing precision declaration")
    if precision.get("name") != PRECISION_NAME:
        raise ValueError("x86 complex/projective acceptance requires Float32")
    if precision.get("rounding") != PRECISION_ROUNDING:
        raise ValueError("unsupported Float32 rounding contract")
    if float(precision.get("epsilon", -1.0)) != F32_EPSILON:
        raise ValueError("unexpected Float32 epsilon")

    complex_cases = corpus.get("complex")
    if not isinstance(complex_cases, dict):
        raise ValueError("missing complex corpus")
    _require_exact_keys(complex_cases, set(COMPARISON_MODES), "complex")
    for case_name, comparison in COMPARISON_MODES.items():
        if complex_cases[case_name].get("comparison") != comparison:
            raise ValueError(
                f"unsupported comparison mode for {case_name}: "
                f"{complex_cases[case_name].get('comparison')!r}"
            )

    exponential = complex_cases["exponential"]
    implementation = exponential.get("implementation")
    if not isinstance(implementation, dict):
        raise ValueError("missing exponential implementation declaration")
    if implementation.get("kind") != EXPONENTIAL_KIND:
        raise ValueError("unsupported exponential implementation kind")
    if int(implementation.get("degree", -1)) != EXPONENTIAL_DEGREE:
        raise ValueError("unsupported exponential degree")
    if (
        float(implementation.get("maximum_input_magnitude", -1.0))
        != EXPONENTIAL_MAXIMUM_INPUT_MAGNITUDE
    ):
        raise ValueError("unsupported exponential approximation radius")
    _require_complex_pair(exponential.get("value"), "complex.exponential.value")
    if abs(complex(*exponential["value"])) > EXPONENTIAL_MAXIMUM_INPUT_MAGNITUDE:
        raise ValueError("complex exponential input exceeds declared approximation domain")

    projective = corpus.get("projective")
    if not isinstance(projective, dict):
        raise ValueError("missing projective corpus")
    _require_exact_keys(projective, PROJECTIVE_CASES, "projective")
    for case_name in (
        "equivalent_real_scale_cp2",
        "equivalent_phase_scale_cp2",
        "non_equivalent_cp2",
    ):
        expected = projective[case_name].get("expected_equivalent")
        if type(expected) is not bool:
            raise ValueError(f"{case_name}.expected_equivalent must be Boolean")

    affine = projective["affine_chart_cp1"]
    if len(affine.get("affine", [])) != 1:
        raise ValueError("current x86 bridge supports the CP1 affine fixture only")
    if len(affine.get("embedded", [])) != 2:
        raise ValueError("CP1 embedded representative must have two coordinates")
    if len(affine.get("expected_round_trip", [])) != 1:
        raise ValueError("CP1 round-trip expectation must have one affine coordinate")
    _require_complex_pair(affine["affine"][0], "affine_chart_cp1.affine[0]")
    _require_complex_pair(affine["embedded"][0], "affine_chart_cp1.embedded[0]")
    _require_complex_pair(affine["embedded"][1], "affine_chart_cp1.embedded[1]")
    _require_complex_pair(
        affine["expected_round_trip"][0],
        "affine_chart_cp1.expected_round_trip[0]",
    )

    infinity = projective["infinity_cp1"]
    if len(infinity.get("representative", [])) != 2:
        raise ValueError("CP1 infinity representative must have two coordinates")
    _require_complex_pair(infinity["representative"][0], "infinity_cp1.representative[0]")
    _require_complex_pair(infinity["representative"][1], "infinity_cp1.representative[1]")
    if type(infinity.get("first_chart_defined")) is not bool:
        raise ValueError("infinity_cp1.first_chart_defined must be Boolean")

    render = corpus.get("render")
    if not isinstance(render, dict):
        raise ValueError("missing render corpus")
    if render.get("field") != RENDER_FIELD:
        raise ValueError("unsupported render field")
    if render.get("coloring") != RENDER_COLORING:
        raise ValueError("unsupported render coloring")
    if render.get("cross_backend_pixel_equality_required") is not False:
        raise ValueError("x86 receipt does not support cross-backend pixel equality")


def exponential_bounds(
    value: list[float],
    degree: int = EXPONENTIAL_DEGREE,
    epsilon: float = F32_EPSILON,
) -> dict[str, float]:
    q_abs = abs(complex(*value))
    truncation = math.exp(q_abs) * q_abs ** (degree + 1) / math.factorial(degree + 1)
    rounding = 64.0 * epsilon * math.exp(q_abs)
    total = truncation + rounding
    if total != truncation + rounding:
        raise AssertionError("exponential total bound is not the recorded sum")
    return {
        "exp_truncation_bound": truncation,
        "exp_float32_rounding_allowance": rounding,
        "exp_total_bound": total,
    }


def _ucomiss(machine: X86, left: int, right: int) -> None:
    machine.bytes(b"\x0f\x2e")
    machine.byte(0xC0 | (left << 3) | right)


def _setne_al(machine: X86) -> None:
    machine.bytes(b"\x0f\x95\xc0")


def _movzx_eax_al(machine: X86) -> None:
    machine.bytes(b"\x0f\xb6\xc0")


def _cvtsi2ss_xmm0_eax(machine: X86) -> None:
    machine.bytes(b"\xf3\x0f\x2a\xc0")


def _emit_nonzero_indicator(
    machine: X86,
    layout: list[str],
    name: str,
    real_displacement: int,
    imaginary_displacement: int,
) -> None:
    """Emit Float32 1.0 iff the stored complex value is nonzero, else 0.0."""
    machine.load_stack_ss(0, real_displacement)
    machine.mulss(0, 0)
    machine.load_stack_ss(1, imaginary_displacement)
    machine.mulss(1, 1)
    machine.addss(0, 1)
    machine.loadss(1, "zero")
    _ucomiss(machine, 0, 1)
    _setne_al(machine)
    _movzx_eax_al(machine)
    _cvtsi2ss_xmm0_eax(machine)
    _store_result(machine, layout, name)


def _emit_embedding_residual(
    machine: X86,
    layout: list[str],
    affine: dict[str, Any],
    scratch: int,
) -> None:
    embedded = affine["embedded"]
    for index, coordinate in enumerate(embedded):
        _register_complex(machine, f"affine_embedded_expected_{index}", coordinate)

    machine.loadss(5, "zero")
    machine.store_stack_ss(5, scratch + 32)
    for index, (real_displacement, imaginary_displacement) in enumerate(
        ((scratch, scratch + 4), (scratch + 8, scratch + 12))
    ):
        machine.load_stack_ss(0, real_displacement)
        machine.load_stack_ss(1, imaginary_displacement)
        machine.loadss(2, f"affine_embedded_expected_{index}_re")
        machine.loadss(3, f"affine_embedded_expected_{index}_im")
        machine.subss(0, 2)
        machine.subss(1, 3)
        machine.mulss(0, 0)
        machine.mulss(1, 1)
        machine.addss(0, 1)
        machine.load_stack_ss(2, scratch + 32)
        machine.addss(0, 2)
        machine.store_stack_ss(0, scratch + 32)
    machine.load_stack_ss(0, scratch + 32)
    _store_result(machine, layout, "affine.embedding_error_squared")


def build_projective_contract_elf(
    corpus: dict[str, Any],
) -> tuple[bytes, list[str]]:
    """Execute CP1 embedding/chart semantics directly in generated x86-64."""
    validate_corpus_contract(corpus)
    projective = corpus["projective"]
    affine = projective["affine_chart_cp1"]
    infinity = projective["infinity_cp1"]

    machine = X86()
    layout: list[str] = []
    reserve = 256
    scratch = 128
    machine.sub_rsp(reserve)
    machine.f32_constant("zero", 0.0)
    machine.f32_constant("one", 1.0)

    # z -> [1:z]. Store the constructed representative and use those stored
    # coordinates for both the corpus-embedded residual and chart extraction.
    _register_complex(machine, "affine_input", affine["affine"][0])
    machine.loadss(0, "one")
    machine.loadss(1, "zero")
    machine.store_stack_ss(0, scratch)
    machine.store_stack_ss(1, scratch + 4)
    _load_complex(machine, "affine_input")
    machine.store_stack_ss(0, scratch + 8)
    machine.store_stack_ss(1, scratch + 12)

    machine.load_stack_ss(0, scratch)
    _store_result(machine, layout, "affine.embedded_first.re")
    machine.load_stack_ss(0, scratch + 4)
    _store_result(machine, layout, "affine.embedded_first.im")
    machine.load_stack_ss(0, scratch + 8)
    _store_result(machine, layout, "affine.embedded_second.re")
    machine.load_stack_ss(0, scratch + 12)
    _store_result(machine, layout, "affine.embedded_second.im")
    _emit_embedding_residual(machine, layout, affine, scratch)

    _emit_nonzero_indicator(
        machine,
        layout,
        "affine.first_chart_defined",
        scratch,
        scratch + 4,
    )

    machine.load_stack_ss(0, scratch + 8)
    machine.load_stack_ss(1, scratch + 12)
    machine.load_stack_ss(2, scratch)
    machine.load_stack_ss(3, scratch + 4)
    _complex_divide(machine)
    _store_result(machine, layout, "affine.first_chart.re")
    _store_result(machine, layout, "affine.first_chart.im", 1)

    # [0:1] (or the corpus-supplied CP1 representative) is handled by an
    # explicit first-coordinate zero test. No division is emitted for this
    # infinity fixture and no NaN/Inf result is interpreted as "undefined".
    _register_complex(machine, "infinity_first", infinity["representative"][0])
    _load_complex(machine, "infinity_first")
    machine.store_stack_ss(0, scratch + 48)
    machine.store_stack_ss(1, scratch + 52)
    _emit_nonzero_indicator(
        machine,
        layout,
        "infinity.first_chart_defined",
        scratch + 48,
        scratch + 52,
    )

    machine.mov_eax(1)
    machine.mov_edi(1)
    machine.rsi_from_rsp()
    machine.mov_edx(len(layout) * 4)
    machine.syscall()
    machine.add_rsp(reserve)
    machine.mov_eax(60)
    machine.mov_edi(0)
    machine.syscall()
    return write_elf(machine.finish()), layout
