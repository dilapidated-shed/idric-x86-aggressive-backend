#!/usr/bin/env python3
import math
from fractions import Fraction
import platform
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from backend.small_scalars import E3M2, build_float_binary_elf, build_float_unary_elf



def dyadic(value: float) -> str:
    fraction = Fraction(value).limit_denominator(16)
    if float(fraction) != value:
        return f"{value:.6f}"
    if fraction.denominator == 1:
        return str(fraction.numerator)
    return f"{fraction.numerator}/{fraction.denominator}"


def reference_text(value: float) -> str:
    fraction = Fraction(value).limit_denominator(16)
    if abs(float(fraction) - value) < 1e-12:
        if fraction.denominator == 1:
            return str(fraction.numerator)
        return f"{fraction.numerator}/{fraction.denominator}"
    return f"{value:.6f}"


def run_payload(image: bytes) -> int:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "candidate"
        path.write_bytes(image)
        path.chmod(0o755)
        run = subprocess.run([path], capture_output=True, check=False)
    if run.returncode != 0:
        raise SystemExit(f"candidate exit={run.returncode} stderr={run.stderr!r}")
    if len(run.stdout) != 1:
        raise SystemExit(f"candidate emitted {len(run.stdout)} bytes, expected 1")
    return run.stdout[0]


@lru_cache(maxsize=None)
def binary(left: int, right: int, operation: str) -> int:
    return run_payload(build_float_binary_elf(E3M2, left, right, operation))


@lru_cache(maxsize=None)
def unary(value: int, operation: str) -> int:
    return run_payload(build_float_unary_elf(E3M2, value, operation))



DAKOTA_DIRECTION = [
    0x08,0x24,0x04,0x28,0x04,0x24,0x04,0x08,0x28,0x04,0x24,0x04,
    0x01,0x21,0x01,0x21,0x01,0x21,0x01,0x21,0x01,0x21,0x01,0x21,0x01,0x21,
]

DAKOTA_JACOBIAN = [
    [0x0c,0x29,0x03,0x00,0x00,0x00,0x27,0x00,0x00,0x0c,0x0c,0x00,0x2a,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x0c,0x26,0x01,0x00,0x00,0x00,0x24,0x00,0x00,0x0c,0x0c,0x00,0x00,0x29,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x0c,0x23,0x00,0x00,0x00,0x00,0x22,0x00,0x00,0x0c,0x0c,0x00,0x00,0x00,0x29,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x0c,0x0c,0x00,0x00,0x00,0x00,0x27,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x0c,0x03,0x00,0x00,0x00,0x00,0x01,0x00,0x00,0x0c,0x0c,0x00,0x00,0x00,0x00,0x00,0x26,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x0c,0x05,0x01,0x00,0x00,0x00,0x02,0x00,0x00,0x0c,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x24,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x0c,0x08,0x02,0x00,0x00,0x00,0x02,0x00,0x00,0x0c,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x23,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x00,0x00,0x00,0x0c,0x28,0x02,0x00,0x00,0x00,0x0c,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    [0x00,0x00,0x00,0x0c,0x25,0x01,0x01,0x00,0x00,0x0c,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x02,0x00,0x00,0x00,0x00,0x00],
    [0x00,0x00,0x00,0x0c,0x23,0x00,0x01,0x00,0x00,0x0c,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x03,0x00,0x00,0x00,0x00],
    [0x00,0x00,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x0c,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x05,0x00,0x00,0x00],
    [0x00,0x00,0x00,0x0c,0x03,0x00,0x21,0x00,0x00,0x0c,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x07,0x00,0x00],
    [0x00,0x00,0x00,0x0c,0x06,0x01,0x23,0x00,0x00,0x0c,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x08,0x00],
    [0x00,0x00,0x00,0x0c,0x09,0x03,0x26,0x00,0x00,0x0c,0x00,0x0c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x09],
]

DAKOTA_JV_REFERENCE = [
    0.5451388472381876,0.5927113334029114,0.4895670078008919,
    0.5289665323810473,0.45372048698916667,0.4731549501099014,
    0.42261242702714896,-0.15357695334574295,-0.08165240496535331,
    -0.05029350042927705,0.018128930745486826,-0.0026210159607702455,
    0.058420594931340275,-0.046822717143564785,
]

DAKOTA_ROW_NAMES = [
    "driver.camber[0]","driver.camber[1]","driver.camber[2]","driver.camber[3]",
    "driver.camber[4]","driver.camber[5]","driver.camber[6]",
    "passenger.camber[0]","passenger.camber[1]","passenger.camber[2]",
    "passenger.camber[3]","passenger.camber[4]","passenger.camber[5]",
    "passenger.camber[6]",
]


def dot26(row: list[int]) -> int:
    accumulator = 0
    for coefficient, direction in zip(row, DAKOTA_DIRECTION):
        product = binary(coefficient, direction, "mul")
        accumulator = binary(product, accumulator, "add")
    return accumulator


def dot2(a: int, b: int, x: int, y: int) -> int:
    ax = binary(a, x, "mul")
    by = binary(b, y, "mul")
    return binary(ax, by, "add")


def rotate_x(cosine: int, sine: int, x: int, y: int) -> int:
    cx = binary(cosine, x, "mul")
    sy = binary(sine, y, "mul")
    return binary(cx, sy, "sub")


def rotate_y(sine: int, cosine: int, x: int, y: int) -> int:
    sx = binary(sine, x, "mul")
    cy = binary(cosine, y, "mul")
    return binary(sx, cy, "add")


def main() -> int:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        print("E3M2 observations require x86_64 Linux direct execution")
        return 0

    one_point_five = 0x0E
    one_half = 0x08
    two = 0x10

    square = binary(one_point_five, one_point_five, "mul")
    cube = binary(square, one_point_five, "mul")

    jacobian_payloads = [dot26(row) for row in DAKOTA_JACOBIAN]

    observed_payloads = [
        binary(one_point_five, one_half, "add"),
        binary(one_point_five, one_half, "sub"),
        binary(one_point_five, one_half, "mul"),
        binary(one_point_five, one_half, "div"),
        square,
        cube,
        unary(two, "sqrt"),
    ] + jacobian_payloads + [
        rotate_x(0x0B, 0x06, 0x12, 0x14),
        rotate_y(0x06, 0x0B, 0x12, 0x14),
        binary(0x14, 0x0E, "mul"),
    ]

    theta = math.radians(360.0 / 17.4)
    caster_multiplier = 1.0 / (2.0 * math.sin(theta))
    front = 1.0
    rear = -0.5
    x = 3.0
    y = 4.0

    cases = [
        ("add 1.5 + 0.5", 1.5 + 0.5),
        ("subtract 1.5 - 0.5", 1.5 - 0.5),
        ("multiply 1.5 * 0.5", 1.5 * 0.5),
        ("divide 1.5 / 0.5", 1.5 / 0.5),
        ("power 1.5^2", 1.5 ** 2),
        ("power 1.5^3", 1.5 ** 3),
        ("sqrt 2", math.sqrt(2.0)),
    ] + [("Jv " + name, value) for name, value in zip(DAKOTA_ROW_NAMES, DAKOTA_JV_REFERENCE)] + [
        ("rotate (3,4) x", math.cos(theta) * x - math.sin(theta) * y),
        ("rotate (3,4) y", math.sin(theta) * x + math.cos(theta) * y),
        ("caster from 4-degree swing", 4.0 * caster_multiplier),
    ]

    print("E3M2 observational measurements: x86-64")
    print(f"theta={math.degrees(theta):.9f} deg  "
          f"sin={math.sin(theta):.9f}  cos={math.cos(theta):.9f}  "
          f"caster_multiplier={caster_multiplier:.9f}")
    print("The numeric residue is observed - reference; it is reported, not graded.")
    print()
    print(f"{'case':31} {'payload':>7} {'reference':>12} {'observed':>12} {'residue':>12}")
    for (label, reference), payload in zip(cases, observed_payloads):
        observed = E3M2.decode(payload)
        residue = observed - reference
        print(f"{label:31} 0x{payload:02x} {reference_text(reference):>12} "
              f"{dyadic(observed):>12} {reference_text(residue):>12}")

    print()
    print("Dakota 14x26 Jacobian exercise:")
    print("  rows: 14 camber observations; columns: 26 named state/nuisance coordinates")
    print("  all 364 partial derivatives are quantized to E3M2 before the matrix product")
    print("  278/364 quantized Jacobian entries are zero at this scale")
    print("  direction: coefficients/geometry/calibration use exact quarters/halves;")
    print("             all 14 steering-offset coordinates use alternating +/-1/16 rad")
    print("  each multiply and each accumulation is requantized to E3M2")
    print("  rotation vector = [3, 4]")
    print("  E3M2 rotation coefficients actually executed: cos=7/8, sin=3/8")
    print("  E3M2 caster multiplier actually executed: 3/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
