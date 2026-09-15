#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import pathlib
import struct
import subprocess
import sys
from typing import Any, Callable

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.complex_projective import (  # noqa: E402
    build_corpus_elf,
    build_render_elf,
    f32,
    floating_error_bound,
)
from backend.complex_projective_contract import (  # noqa: E402
    COMPARISON_MODES,
    EXPONENTIAL_DEGREE,
    EXPONENTIAL_KIND,
    EXPONENTIAL_MAXIMUM_INPUT_MAGNITUDE,
    PRECISION_ROUNDING,
    RENDER_COLORING,
    RENDER_FIELD,
    build_projective_contract_elf,
    exponential_bounds,
    validate_corpus_contract,
)


def run_candidate(path: pathlib.Path) -> bytes:
    result = subprocess.run(
        [str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if result.returncode != 0:
        error = result.stderr.decode(errors="replace")
        raise RuntimeError(f"candidate {path.name} exited {result.returncode}: {error}")
    return result.stdout


def exact_f32(actual: float, expected: float) -> None:
    if struct.pack("<f", actual) != struct.pack("<f", f32(expected)):
        raise AssertionError(
            f"exact Float32 mismatch: {actual!r} != {f32(expected)!r}"
        )


def close(actual: float, expected: float, tolerance: float) -> None:
    if not math.isfinite(actual) or abs(actual - expected) > tolerance:
        raise AssertionError(
            f"floating mismatch: {actual!r} vs {expected!r}, tolerance {tolerance!r}"
        )


def pair(values: tuple[float, ...], names: list[str], prefix: str) -> complex:
    return complex(
        values[names.index(prefix + ".re")],
        values[names.index(prefix + ".im")],
    )


def _projective_expectation(
    *,
    label: str,
    residual: float,
    tolerance: float,
    expected_equivalent: bool,
) -> bool:
    if not math.isfinite(residual):
        raise AssertionError(f"{label} residual is not finite: {residual!r}")
    observed_equivalent = abs(residual) <= tolerance
    if observed_equivalent != expected_equivalent:
        raise AssertionError(
            f"{label} observed_equivalent={observed_equivalent} "
            f"but corpus expected_equivalent={expected_equivalent}; "
            f"residual={residual!r}, tolerance={tolerance!r}"
        )
    return observed_equivalent


def validate_numerical(
    corpus: dict[str, Any],
    names: list[str],
    values: tuple[float, ...],
) -> dict[str, float]:
    complex_cases = corpus["complex"]
    epsilon = float(corpus["precision"]["epsilon"])

    for key in ["add", "multiply", "conjugate", "power_two", "polynomial"]:
        actual = pair(values, names, key)
        expected = complex_cases[key]["expected"]
        exact_f32(actual.real, expected[0])
        exact_f32(actual.imag, expected[1])

    exact_f32(
        values[names.index("magnitude_squared")],
        complex_cases["magnitude_squared"]["expected"],
    )

    for key in ["reciprocal", "divide", "rational"]:
        actual = pair(values, names, key)
        expected = complex(*complex_cases[key]["expected"])
        tolerance = floating_error_bound(expected, 32, epsilon)
        close(actual.real, expected.real, tolerance)
        close(actual.imag, expected.imag, tolerance)

    exponential = complex_cases["exponential"]
    actual_exp = pair(values, names, "exponential")
    expected_exp = complex(*exponential["expected_oracle"])
    bounds = exponential_bounds(
        exponential["value"],
        int(exponential["implementation"]["degree"]),
        epsilon,
    )
    if bounds["exp_total_bound"] != (
        bounds["exp_truncation_bound"]
        + bounds["exp_float32_rounding_allowance"]
    ):
        raise AssertionError("recorded exponential total is not the sum of its parts")
    if abs(actual_exp - expected_exp) > bounds["exp_total_bound"]:
        raise AssertionError(
            f"exp error {abs(actual_exp - expected_exp)} exceeds derived bound "
            f"{bounds['exp_total_bound']}"
        )

    polar = complex_cases["polar_round_trip"]
    polar_tolerance = 64 * epsilon * max(
        1.0, float(polar["expected_magnitude_oracle"])
    )
    close(
        values[names.index("polar.magnitude")],
        float(polar["expected_magnitude_oracle"]),
        polar_tolerance,
    )
    close(
        values[names.index("polar.phase_turns")],
        float(polar["expected_phase_turns"]),
        64 * epsilon,
    )
    close(
        values[names.index("polar.round_trip_re")],
        float(polar["cartesian"][0]),
        polar_tolerance,
    )
    close(
        values[names.index("polar.round_trip_im")],
        float(polar["cartesian"][1]),
        polar_tolerance,
    )

    projective = corpus["projective"]
    real_residual = values[
        names.index("projective.real_scale.rescaling_error_squared")
    ]
    phase_residual = values[
        names.index("projective.phase_scale.rescaling_error_squared")
    ]
    wedge_residual = values[
        names.index("projective.non_equivalent.wedge_error_squared")
    ]

    _projective_expectation(
        label="equivalent_real_scale_cp2",
        residual=real_residual,
        tolerance=64 * epsilon,
        expected_equivalent=projective["equivalent_real_scale_cp2"][
            "expected_equivalent"
        ],
    )
    _projective_expectation(
        label="equivalent_phase_scale_cp2",
        residual=phase_residual,
        tolerance=64 * epsilon,
        expected_equivalent=projective["equivalent_phase_scale_cp2"][
            "expected_equivalent"
        ],
    )
    _projective_expectation(
        label="non_equivalent_cp2",
        residual=wedge_residual,
        tolerance=1024 * epsilon,
        expected_equivalent=projective["non_equivalent_cp2"][
            "expected_equivalent"
        ],
    )

    # The older numerical candidate still extracts the chart from the corpus's
    # embedded representative. Keep this result checked, but the acceptance
    # round-trip claim comes only from complex-projective-contract.elf below.
    affine_expected = projective["affine_chart_cp1"]["expected_round_trip"][0]
    exact_f32(values[names.index("affine_chart.re")], affine_expected[0])
    exact_f32(values[names.index("affine_chart.im")], affine_expected[1])

    return {
        **bounds,
        "projective_real_scale_residual_squared": real_residual,
        "projective_phase_scale_residual_squared": phase_residual,
        "projective_wedge_residual_squared": wedge_residual,
    }


def validate_projective_contract(
    corpus: dict[str, Any],
    names: list[str],
    values: tuple[float, ...],
) -> dict[str, float]:
    projective = corpus["projective"]
    affine = projective["affine_chart_cp1"]
    embedded = affine["embedded"]

    exact_f32(
        values[names.index("affine.embedded_first.re")],
        embedded[0][0],
    )
    exact_f32(
        values[names.index("affine.embedded_first.im")],
        embedded[0][1],
    )
    exact_f32(
        values[names.index("affine.embedded_second.re")],
        embedded[1][0],
    )
    exact_f32(
        values[names.index("affine.embedded_second.im")],
        embedded[1][1],
    )

    embedding_error = values[names.index("affine.embedding_error_squared")]
    exact_f32(embedding_error, 0.0)
    exact_f32(values[names.index("affine.first_chart_defined")], 1.0)

    round_trip = affine["expected_round_trip"][0]
    affine_input = affine["affine"][0]
    if round_trip != affine_input:
        raise AssertionError(
            "current corpus says affine chart round trip differs from affine input"
        )
    exact_f32(
        values[names.index("affine.first_chart.re")],
        round_trip[0],
    )
    exact_f32(
        values[names.index("affine.first_chart.im")],
        round_trip[1],
    )

    expected_defined = projective["infinity_cp1"]["first_chart_defined"]
    actual_defined = values[names.index("infinity.first_chart_defined")]
    exact_f32(actual_defined, 1.0 if expected_defined else 0.0)

    return {
        "affine_embedding_error_squared": embedding_error,
        "cp1_infinity_first_chart_defined": actual_defined,
    }


def _expect_rejected(label: str, function: Callable[[], Any]) -> None:
    try:
        function()
    except (ValueError, AssertionError, KeyError, TypeError):
        return
    raise AssertionError(f"semantic discriminator mutation was accepted: {label}")


def fail_closed_discriminator_checks(
    corpus: dict[str, Any],
    numerical_names: list[str],
    numerical_values: tuple[float, ...],
    projective_names: list[str],
    projective_values: tuple[float, ...],
) -> None:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("schema", lambda c: c.__setitem__("schema", "unknown-schema")),
        (
            "precision.name",
            lambda c: c["precision"].__setitem__("name", "Float64"),
        ),
        (
            "precision.rounding",
            lambda c: c["precision"].__setitem__("rounding", "toward-zero"),
        ),
        (
            "comparison",
            lambda c: c["complex"]["add"].__setitem__("comparison", "floating"),
        ),
        (
            "exponential.kind",
            lambda c: c["complex"]["exponential"]["implementation"].__setitem__(
                "kind", "unknown"
            ),
        ),
        (
            "exponential.degree",
            lambda c: c["complex"]["exponential"]["implementation"].__setitem__(
                "degree", 8
            ),
        ),
        (
            "exponential.maximum_input_magnitude",
            lambda c: c["complex"]["exponential"]["implementation"].__setitem__(
                "maximum_input_magnitude", 0.75
            ),
        ),
        (
            "render.field",
            lambda c: c["render"].__setitem__("field", "unknown"),
        ),
        (
            "render.coloring",
            lambda c: c["render"].__setitem__("coloring", "unknown"),
        ),
    ]
    for label, mutate in mutations:
        changed = copy.deepcopy(corpus)
        mutate(changed)
        _expect_rejected(label, lambda changed=changed: validate_corpus_contract(changed))

    outside_exp = copy.deepcopy(corpus)
    outside_exp["complex"]["exponential"]["value"] = [0.5001, 0.0]
    _expect_rejected(
        "standalone exponential outside radius",
        lambda: validate_corpus_contract(outside_exp),
    )

    outside_render = copy.deepcopy(corpus)
    outside_render["render"]["entire_q"]["constant"] = [0.6, 0.0]
    _expect_rejected(
        "render q(z) outside radius",
        lambda: build_render_elf(outside_render),
    )

    contradictory_projective = copy.deepcopy(corpus)
    contradictory_projective["projective"]["equivalent_real_scale_cp2"][
        "expected_equivalent"
    ] = False
    _expect_rejected(
        "expected_equivalent",
        lambda: validate_numerical(
            contradictory_projective,
            numerical_names,
            numerical_values,
        ),
    )

    contradictory_chart = copy.deepcopy(corpus)
    contradictory_chart["projective"]["infinity_cp1"]["first_chart_defined"] = True
    _expect_rejected(
        "first_chart_defined",
        lambda: validate_projective_contract(
            contradictory_chart,
            projective_names,
            projective_values,
        ),
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unpack_floats(output: bytes, names: list[str], label: str) -> tuple[float, ...]:
    if len(output) % 4:
        raise AssertionError(f"{label} output length is not a Float32 multiple")
    values = struct.unpack("<" + "f" * (len(output) // 4), output)
    if len(values) != len(names):
        raise AssertionError(f"{label} result layout length mismatch")
    return values


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--backend-sha", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument(
        "--idric-sha", default=os.environ.get("IDRIC_COMPLEX_SHA", "unknown")
    )
    args = parser.parse_args()

    corpus_path = pathlib.Path(args.corpus)
    artifacts = pathlib.Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    corpus = json.loads(corpus_path.read_text())
    validate_corpus_contract(corpus)

    corpus_elf, numerical_names = build_corpus_elf(corpus)
    projective_elf, projective_names = build_projective_contract_elf(corpus)
    render_elf, header = build_render_elf(corpus)

    candidates = {
        "complex-corpus.elf": corpus_elf,
        "complex-projective-contract.elf": projective_elf,
        "complex-render.elf": render_elf,
    }
    for filename, data in candidates.items():
        path = artifacts / filename
        path.write_bytes(data)
        path.chmod(0o755)

    numerical_path = artifacts / "complex-corpus.elf"
    numerical_first = run_candidate(numerical_path)
    numerical_second = run_candidate(numerical_path)
    if numerical_first != numerical_second:
        raise AssertionError("complex corpus candidate is not byte-deterministic")
    numerical_values = _unpack_floats(
        numerical_first, numerical_names, "complex corpus"
    )
    numerical_checks = validate_numerical(
        corpus, numerical_names, numerical_values
    )
    (artifacts / "complex-corpus.bin").write_bytes(numerical_first)

    projective_path = artifacts / "complex-projective-contract.elf"
    projective_first = run_candidate(projective_path)
    projective_second = run_candidate(projective_path)
    if projective_first != projective_second:
        raise AssertionError("projective contract candidate is not byte-deterministic")
    projective_values = _unpack_floats(
        projective_first, projective_names, "projective contract"
    )
    projective_checks = validate_projective_contract(
        corpus, projective_names, projective_values
    )
    (artifacts / "complex-projective-contract.bin").write_bytes(projective_first)

    render_path = artifacts / "complex-render.elf"
    scene_first = run_candidate(render_path)
    scene_second = run_candidate(render_path)
    if scene_first != scene_second:
        raise AssertionError("headless render is not byte-deterministic")
    if not scene_first.startswith(header):
        raise AssertionError("render did not emit expected PPM header")
    payload = scene_first[len(header) :]
    expected_payload = int(corpus["render"]["width"]) * int(
        corpus["render"]["height"]
    ) * 3
    if len(payload) != expected_payload:
        raise AssertionError("render payload length mismatch")
    if len(set(payload)) < 64 or min(payload) == max(payload):
        raise AssertionError("render did not exercise varying complex state")
    (artifacts / "complex-projective-scene.ppm").write_bytes(scene_first)

    fail_closed_discriminator_checks(
        corpus,
        numerical_names,
        numerical_values,
        projective_names,
        projective_values,
    )

    corpus_source = corpus_path.read_bytes()
    tested_checkout = _git_head()
    detailed_stages = {
        "direct_backend_generation": "PASS",
        "native_execution": "PASS",
        "complex_arithmetic": "PASS",
        "projective_explicit_rescaling": "PASS",
        "projective_invariant_non_equivalence": "PASS",
        "affine_embedding": "PASS",
        "finite_first_chart_extraction": "PASS",
        "cp1_infinity_undefined_first_chart": "PASS",
        "bounded_complex_exponential": "PASS",
        "deterministic_R_exp_render": "PASS",
        "deterministic_regeneration": "PASS",
        "semantic_discriminators_fail_closed": "PASS",
        # Required aggregate names for the merged ai-ci v1 policy. They are
        # valid only because the detailed sub-stages above all passed.
        "numerical_corpus": "PASS",
        "projective_corpus": "PASS",
        "headless_render": "PASS",
    }
    receipt = {
        "schema": "idric-x86-complex-projective-receipt-v2",
        "backend_repository": "isomorphisms/idric-x86-aggressive-backend",
        "backend_sha": args.backend_sha,
        "tested_checkout_sha": tested_checkout,
        "idric_repository": "isomorphisms/Idric",
        "idric_sha": args.idric_sha,
        "corpus_sha256": _sha256(corpus_source),
        "precision": corpus["precision"]["name"],
        "precision_rounding": corpus["precision"]["rounding"],
        "candidate": (
            "direct ELF64 x86-64; scalar SSE + observational x87; "
            "no C/assembler/linker/libc/libm"
        ),
        "semantic_discriminators": {
            "comparison_modes": COMPARISON_MODES,
            "exponential_kind": EXPONENTIAL_KIND,
            "exponential_degree": EXPONENTIAL_DEGREE,
            "exponential_maximum_input_magnitude": (
                EXPONENTIAL_MAXIMUM_INPUT_MAGNITUDE
            ),
            "render_field": RENDER_FIELD,
            "render_coloring": RENDER_COLORING,
            "cross_backend_pixel_equality_required": False,
        },
        "stages": detailed_stages,
        "complex_corpus_elf_sha256": _sha256(corpus_elf),
        "complex_corpus_output_sha256": _sha256(numerical_first),
        "projective_contract_elf_sha256": _sha256(projective_elf),
        "projective_contract_output_sha256": _sha256(projective_first),
        "render_elf_sha256": _sha256(render_elf),
        "render_ppm_sha256": _sha256(scene_first),
        "render_statistics": {
            "payload_bytes": len(payload),
            "minimum_byte": min(payload),
            "maximum_byte": max(payload),
            "distinct_byte_values": len(set(payload)),
            "mean_byte": sum(payload) / len(payload),
        },
        "derived_bounds": {
            **numerical_checks,
            **projective_checks,
        },
        "cp1_infinity_strategy": (
            "candidate zero-tests first homogeneous coordinate and emits only "
            "first_chart_defined; no infinity chart division/result is emitted"
        ),
    }
    (artifacts / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )

    with (artifacts / "acceptance-receipt.tsv").open("w") as output:
        output.write("COMPLEX_PROJECTIVE_RECEIPT\t1\n")
        output.write("role\tX86_LEADER\n")
        output.write("repository\tisomorphisms/idric-x86-aggressive-backend\n")
        output.write(f"source_head_sha\t{args.backend_sha}\n")
        output.write(f"tested_checkout_sha\t{tested_checkout}\n")
        output.write(
            f"canonical_complex_projective_semantics_sha\t{args.idric_sha}\n"
        )
        output.write(f"corpus_sha256\t{receipt['corpus_sha256']}\n")
        output.write(
            f"complex_corpus_elf_sha256\t{receipt['complex_corpus_elf_sha256']}\n"
        )
        output.write(
            "projective_contract_elf_sha256\t"
            f"{receipt['projective_contract_elf_sha256']}\n"
        )
        output.write(f"render_elf_sha256\t{receipt['render_elf_sha256']}\n")
        output.write(f"render_ppm_sha256\t{receipt['render_ppm_sha256']}\n")
        output.write(
            "exp_truncation_bound\t"
            f"{numerical_checks['exp_truncation_bound']:.17g}\n"
        )
        output.write(
            "exp_float32_rounding_allowance\t"
            f"{numerical_checks['exp_float32_rounding_allowance']:.17g}\n"
        )
        output.write(
            "exp_total_bound\t"
            f"{numerical_checks['exp_total_bound']:.17g}\n"
        )
        output.write(
            "candidate\tdirect ELF64 x86-64; scalar SSE plus observational "
            "x87; no C assembler linker libc libm RefC LLVM\n"
        )
        for stage, status in detailed_stages.items():
            output.write(f"stage\t{stage}\t{status}\n")

    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
