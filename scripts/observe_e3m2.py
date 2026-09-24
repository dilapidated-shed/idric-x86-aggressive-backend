#!/usr/bin/env python3
import math
import platform
import subprocess
import tempfile
from pathlib import Path

from backend.small_scalars import E3M2, build_float_binary_elf, build_float_unary_elf


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


def binary(left: int, right: int, operation: str) -> int:
    return run_payload(build_float_binary_elf(E3M2, left, right, operation))


def unary(value: int, operation: str) -> int:
    return run_payload(build_float_unary_elf(E3M2, value, operation))


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

    observed_payloads = [
        binary(one_point_five, one_half, "add"),
        binary(one_point_five, one_half, "sub"),
        binary(one_point_five, one_half, "mul"),
        binary(one_point_five, one_half, "div"),
        square,
        cube,
        unary(two, "sqrt"),
        dot2(0x2D, 0x2A, 0x0C, 0x28),
        dot2(0x2C, 0x0C, 0x0C, 0x28),
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
        ("Jacobian delta camber", -1.3 * front + -0.7 * rear),
        ("Jacobian delta caster", -1.0 * front + 1.0 * rear),
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
        print(f"{label:31} 0x{payload:02x} {reference:12.6f} "
              f"{observed:12.6f} {residue:12.6f}")

    print()
    print("Physical inputs before E3M2 quantization:")
    print("  adjustment Jacobian = [[-1.3, -0.7], [-1, 1]], vector = [1, -0.5]")
    print("  rotation vector = [3, 4]")
    print("  E3M2 rotation coefficients actually executed: cos=0.875, sin=0.375")
    print("  E3M2 caster multiplier actually executed: 1.5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
