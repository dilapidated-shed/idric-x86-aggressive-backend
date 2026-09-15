"""Direct x86-64 Float32 complex/projective numerical oracle.

Python in this module is a machine-code generator and an external test oracle.
Candidate arithmetic is executed by the generated ELF64 program itself. The
candidate uses baseline scalar SSE instructions and Linux x86-64 syscalls; it
has no C, assembler, linker, libc, libm, RefC, or dynamic loader dependency.
"""
from __future__ import annotations

import math
import struct
from typing import Any

from backend.elf64 import write_elf

F32_EPSILON = 2.0 ** -23


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


class X86:
    """Tiny label-aware encoder for the instructions used by this oracle."""

    def __init__(self) -> None:
        self.code = bytearray()
        self.patches: list[tuple[int, str]] = []
        self.data: list[tuple[str, bytes]] = []
        self._data_names: set[str] = set()

    def bytes(self, value: bytes) -> None:
        self.code.extend(value)

    def byte(self, value: int) -> None:
        self.code.append(value)

    def rip32(self, label: str) -> None:
        position = len(self.code)
        self.code.extend(b"\x00" * 4)
        self.patches.append((position, label))

    def f32_constant(self, label: str, value: float) -> None:
        if label in self._data_names:
            return
        self._data_names.add(label)
        self.data.append((label, struct.pack("<f", value)))

    def data_bytes(self, label: str, value: bytes) -> None:
        if label in self._data_names:
            raise ValueError(f"duplicate data label {label}")
        self._data_names.add(label)
        self.data.append((label, value))

    def loadss(self, register: int, label: str) -> None:
        self.bytes(b"\xF3\x0F\x10")
        self.byte(0x05 | (register << 3))
        self.rip32(label)

    def movss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x10")
        self.byte(0xC0 | (destination << 3) | source)

    def addss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x58")
        self.byte(0xC0 | (destination << 3) | source)

    def subss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x5C")
        self.byte(0xC0 | (destination << 3) | source)

    def mulss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x59")
        self.byte(0xC0 | (destination << 3) | source)

    def divss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x5E")
        self.byte(0xC0 | (destination << 3) | source)

    def sqrtss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x51")
        self.byte(0xC0 | (destination << 3) | source)

    def minss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x5D")
        self.byte(0xC0 | (destination << 3) | source)

    def maxss(self, destination: int, source: int) -> None:
        self.bytes(b"\xF3\x0F\x5F")
        self.byte(0xC0 | (destination << 3) | source)

    def store_stack_ss(self, register: int, displacement: int) -> None:
        self.bytes(b"\xF3\x0F\x11")
        self.byte(0x84 | (register << 3))
        self.byte(0x24)
        self.bytes(struct.pack("<i", displacement))

    def load_stack_ss(self, register: int, displacement: int) -> None:
        self.bytes(b"\xF3\x0F\x10")
        self.byte(0x84 | (register << 3))
        self.byte(0x24)
        self.bytes(struct.pack("<i", displacement))

    def store_stack_byte_al(self, displacement: int) -> None:
        self.bytes(b"\x88\x84\x24" + struct.pack("<i", displacement))

    def cvttss2si_eax(self, source: int) -> None:
        self.bytes(b"\xF3\x0F\x2C")
        self.byte(0xC0 | source)

    def sub_rsp(self, size: int) -> None:
        self.bytes(b"\x48\x81\xEC" + struct.pack("<I", size))

    def add_rsp(self, size: int) -> None:
        self.bytes(b"\x48\x81\xC4" + struct.pack("<I", size))

    def mov_eax(self, value: int) -> None:
        self.bytes(b"\xB8" + struct.pack("<I", value & 0xFFFFFFFF))

    def mov_edi(self, value: int) -> None:
        self.bytes(b"\xBF" + struct.pack("<I", value & 0xFFFFFFFF))

    def mov_edx(self, value: int) -> None:
        self.bytes(b"\xBA" + struct.pack("<I", value & 0xFFFFFFFF))

    def rsi_from_rsp(self) -> None:
        self.bytes(b"\x48\x89\xE6")

    def lea_rsi_rip(self, label: str) -> None:
        self.bytes(b"\x48\x8D\x35")
        self.rip32(label)

    def syscall(self) -> None:
        self.bytes(b"\x0F\x05")

    # x87 is used only for observational phase/sine/cosine. Evolving
    # holomorphic state and bounded exp(q) remain SSE arithmetic without
    # conjugation/magnitude/phase feedback.
    def x87_fld_rip(self, label: str) -> None:
        self.bytes(b"\xD9\x05")
        self.rip32(label)

    def x87_fld_stack(self, displacement: int) -> None:
        self.bytes(b"\xD9\x84\x24" + struct.pack("<i", displacement))

    def x87_fstp_stack(self, displacement: int) -> None:
        self.bytes(b"\xD9\x9C\x24" + struct.pack("<i", displacement))

    def x87_fpatan(self) -> None:
        self.bytes(b"\xD9\xF3")

    def x87_fsin(self) -> None:
        self.bytes(b"\xD9\xFE")

    def x87_fcos(self) -> None:
        self.bytes(b"\xD9\xFF")

    def finish(self) -> bytes:
        while len(self.code) % 4:
            self.code.append(0x90)
        labels: dict[str, int] = {}
        body = bytearray(self.code)
        for label, value in self.data:
            labels[label] = len(body)
            body.extend(value)
        for position, label in self.patches:
            if label not in labels:
                raise ValueError(f"missing data label {label}")
            displacement = labels[label] - (position + 4)
            body[position : position + 4] = struct.pack("<i", displacement)
        return bytes(body)


def _complex_multiply(machine: X86) -> None:
    """(xmm0,xmm1) *= (xmm2,xmm3), preserving xmm2/xmm3."""
    machine.movss(4, 0)
    machine.mulss(4, 2)
    machine.movss(5, 1)
    machine.mulss(5, 3)
    machine.subss(4, 5)
    machine.movss(6, 0)
    machine.mulss(6, 3)
    machine.movss(7, 1)
    machine.mulss(7, 2)
    machine.addss(6, 7)
    machine.movss(0, 4)
    machine.movss(1, 6)


def _complex_divide(machine: X86) -> None:
    """(xmm0,xmm1) /= (xmm2,xmm3), preserving xmm2/xmm3."""
    machine.movss(6, 2)
    machine.mulss(6, 2)
    machine.movss(7, 3)
    machine.mulss(7, 3)
    machine.addss(6, 7)
    machine.movss(4, 0)
    machine.mulss(4, 2)
    machine.movss(5, 1)
    machine.mulss(5, 3)
    machine.addss(4, 5)
    machine.movss(7, 1)
    machine.mulss(7, 2)
    machine.movss(5, 0)
    machine.mulss(5, 3)
    machine.subss(7, 5)
    machine.divss(4, 6)
    machine.divss(7, 6)
    machine.movss(0, 4)
    machine.movss(1, 7)


def _load_complex(machine: X86, prefix: str) -> None:
    machine.loadss(0, prefix + "_re")
    machine.loadss(1, prefix + "_im")


def _load_complex_rhs(machine: X86, prefix: str) -> None:
    machine.loadss(2, prefix + "_re")
    machine.loadss(3, prefix + "_im")


def _add_complex_constant(machine: X86, prefix: str) -> None:
    machine.loadss(4, prefix + "_re")
    machine.addss(0, 4)
    machine.loadss(4, prefix + "_im")
    machine.addss(1, 4)


def _register_complex(machine: X86, prefix: str, value: list[float]) -> None:
    machine.f32_constant(prefix + "_re", float(value[0]))
    machine.f32_constant(prefix + "_im", float(value[1]))


def _emit_exp_taylor(machine: X86, q_prefix: str, degree: int) -> None:
    if degree < 1:
        raise ValueError("complex exponential degree must be positive")
    _load_complex_rhs(machine, q_prefix)
    coefficients = [1.0 / math.factorial(k) for k in range(degree, -1, -1)]
    for index, coefficient in enumerate(coefficients):
        machine.f32_constant(f"exp_coefficient_{degree}_{index}", coefficient)
    machine.loadss(0, f"exp_coefficient_{degree}_0")
    machine.loadss(1, "zero")
    for index in range(1, len(coefficients)):
        _complex_multiply(machine)
        machine.loadss(4, f"exp_coefficient_{degree}_{index}")
        machine.addss(0, 4)


def _store_result(machine: X86, layout: list[str], name: str, register: int = 0) -> None:
    machine.store_stack_ss(register, len(layout) * 4)
    layout.append(name)


def _emit_projective_rescaling_error(
    machine: X86,
    layout: list[str],
    name: str,
    left: list[list[float]],
    scale: list[float],
    right: list[list[float]],
    scratch: int,
) -> None:
    if len(left) != len(right):
        raise ValueError("projective representatives must have equal coordinate count")
    _register_complex(machine, name + "_scale", scale)
    machine.loadss(5, "zero")
    machine.store_stack_ss(5, scratch)
    for index, (left_coordinate, right_coordinate) in enumerate(zip(left, right)):
        lp = f"{name}_left_{index}"
        rp = f"{name}_right_{index}"
        _register_complex(machine, lp, left_coordinate)
        _register_complex(machine, rp, right_coordinate)
        _load_complex(machine, lp)
        _load_complex_rhs(machine, name + "_scale")
        _complex_multiply(machine)
        machine.loadss(2, rp + "_re")
        machine.loadss(3, rp + "_im")
        machine.subss(0, 2)
        machine.subss(1, 3)
        machine.mulss(0, 0)
        machine.mulss(1, 1)
        machine.addss(0, 1)
        machine.load_stack_ss(2, scratch)
        machine.addss(0, 2)
        machine.store_stack_ss(0, scratch)
    machine.load_stack_ss(0, scratch)
    _store_result(machine, layout, name + ".rescaling_error_squared")


def _emit_projective_wedge_error(
    machine: X86,
    layout: list[str],
    name: str,
    left: list[list[float]],
    right: list[list[float]],
    scratch: int,
) -> None:
    if len(left) != len(right):
        raise ValueError("projective representatives must have equal coordinate count")
    for index, coordinate in enumerate(left):
        _register_complex(machine, f"{name}_left_{index}", coordinate)
    for index, coordinate in enumerate(right):
        _register_complex(machine, f"{name}_right_{index}", coordinate)
    machine.loadss(5, "zero")
    machine.store_stack_ss(5, scratch)
    for i in range(len(left)):
        for j in range(i + 1, len(left)):
            _load_complex(machine, f"{name}_left_{i}")
            _load_complex_rhs(machine, f"{name}_right_{j}")
            _complex_multiply(machine)
            machine.store_stack_ss(0, scratch + 4)
            machine.store_stack_ss(1, scratch + 8)
            _load_complex(machine, f"{name}_left_{j}")
            _load_complex_rhs(machine, f"{name}_right_{i}")
            _complex_multiply(machine)
            machine.load_stack_ss(2, scratch + 4)
            machine.load_stack_ss(3, scratch + 8)
            machine.subss(2, 0)
            machine.subss(3, 1)
            machine.mulss(2, 2)
            machine.mulss(3, 3)
            machine.addss(2, 3)
            machine.load_stack_ss(0, scratch)
            machine.addss(0, 2)
            machine.store_stack_ss(0, scratch)
    machine.load_stack_ss(0, scratch)
    _store_result(machine, layout, name + ".wedge_error_squared")


def build_corpus_elf(corpus: dict[str, Any]) -> tuple[bytes, list[str]]:
    if corpus.get("schema") != "idric-complex-projective-corpus-v1":
        raise ValueError("unsupported complex/projective corpus schema")
    if corpus["precision"]["name"] != "Float32":
        raise ValueError("x86 leading corpus currently requires declared Float32")

    machine = X86()
    layout: list[str] = []
    reserve = 512
    scratch = 384
    machine.sub_rsp(reserve)
    machine.f32_constant("zero", 0.0)
    machine.f32_constant("one", 1.0)
    machine.f32_constant("minus_one", -1.0)
    machine.f32_constant("tau", math.tau)
    complex_cases = corpus["complex"]

    add = complex_cases["add"]
    _register_complex(machine, "add_left", add["left"])
    _register_complex(machine, "add_right", add["right"])
    _load_complex(machine, "add_left")
    _load_complex_rhs(machine, "add_right")
    machine.addss(0, 2)
    machine.addss(1, 3)
    _store_result(machine, layout, "add.re")
    _store_result(machine, layout, "add.im", 1)

    multiply = complex_cases["multiply"]
    _register_complex(machine, "multiply_left", multiply["left"])
    _register_complex(machine, "multiply_right", multiply["right"])
    _load_complex(machine, "multiply_left")
    _load_complex_rhs(machine, "multiply_right")
    _complex_multiply(machine)
    _store_result(machine, layout, "multiply.re")
    _store_result(machine, layout, "multiply.im", 1)

    reciprocal = complex_cases["reciprocal"]
    _register_complex(machine, "reciprocal_value", reciprocal["value"])
    machine.loadss(0, "one")
    machine.loadss(1, "zero")
    _load_complex_rhs(machine, "reciprocal_value")
    _complex_divide(machine)
    _store_result(machine, layout, "reciprocal.re")
    _store_result(machine, layout, "reciprocal.im", 1)

    divide = complex_cases["divide"]
    _register_complex(machine, "divide_numerator", divide["numerator"])
    _register_complex(machine, "divide_denominator", divide["denominator"])
    _load_complex(machine, "divide_numerator")
    _load_complex_rhs(machine, "divide_denominator")
    _complex_divide(machine)
    _store_result(machine, layout, "divide.re")
    _store_result(machine, layout, "divide.im", 1)

    conjugate = complex_cases["conjugate"]
    _register_complex(machine, "conjugate_value", conjugate["value"])
    _load_complex(machine, "conjugate_value")
    machine.loadss(2, "minus_one")
    machine.mulss(1, 2)
    _store_result(machine, layout, "conjugate.re")
    _store_result(machine, layout, "conjugate.im", 1)

    magnitude = complex_cases["magnitude_squared"]
    _register_complex(machine, "magnitude_value", magnitude["value"])
    _load_complex(machine, "magnitude_value")
    machine.mulss(0, 0)
    machine.mulss(1, 1)
    machine.addss(0, 1)
    _store_result(machine, layout, "magnitude_squared")

    power = complex_cases["power_two"]
    _register_complex(machine, "power_value", power["value"])
    _load_complex(machine, "power_value")
    _load_complex_rhs(machine, "power_value")
    _complex_multiply(machine)
    _store_result(machine, layout, "power_two.re")
    _store_result(machine, layout, "power_two.im", 1)

    polynomial = complex_cases["polynomial"]
    _register_complex(machine, "polynomial_value", polynomial["value"])
    coefficients = polynomial["coefficients_low_to_high"]
    for index, coefficient in enumerate(coefficients):
        _register_complex(machine, f"polynomial_coefficient_{index}", coefficient)
    last = len(coefficients) - 1
    _load_complex(machine, f"polynomial_coefficient_{last}")
    for index in range(last - 1, -1, -1):
        _load_complex_rhs(machine, "polynomial_value")
        _complex_multiply(machine)
        _add_complex_constant(machine, f"polynomial_coefficient_{index}")
    _store_result(machine, layout, "polynomial.re")
    _store_result(machine, layout, "polynomial.im", 1)

    rational = complex_cases["rational"]
    _register_complex(machine, "rational_value", rational["value"])
    _register_complex(machine, "rational_zero", rational["zero"])
    _register_complex(machine, "rational_pole", rational["pole"])
    _load_complex(machine, "rational_value")
    _load_complex_rhs(machine, "rational_zero")
    machine.subss(0, 2)
    machine.subss(1, 3)
    machine.store_stack_ss(0, scratch + 16)
    machine.store_stack_ss(1, scratch + 20)
    _load_complex(machine, "rational_value")
    _load_complex_rhs(machine, "rational_pole")
    machine.subss(0, 2)
    machine.subss(1, 3)
    machine.movss(2, 0)
    machine.movss(3, 1)
    machine.load_stack_ss(0, scratch + 16)
    machine.load_stack_ss(1, scratch + 20)
    _complex_divide(machine)
    _store_result(machine, layout, "rational.re")
    _store_result(machine, layout, "rational.im", 1)

    exponential = complex_cases["exponential"]
    _register_complex(machine, "exponential_value", exponential["value"])
    exp_spec = exponential["implementation"]
    q_abs = abs(complex(*exponential["value"]))
    if q_abs > float(exp_spec["maximum_input_magnitude"]):
        raise ValueError("complex exponential input exceeds declared approximation domain")
    _emit_exp_taylor(machine, "exponential_value", int(exp_spec["degree"]))
    _store_result(machine, layout, "exponential.re")
    _store_result(machine, layout, "exponential.im", 1)

    polar = complex_cases["polar_round_trip"]
    _register_complex(machine, "polar_cartesian", polar["cartesian"])
    _load_complex(machine, "polar_cartesian")
    machine.movss(4, 0)
    machine.mulss(4, 0)
    machine.movss(5, 1)
    machine.mulss(5, 1)
    machine.addss(4, 5)
    machine.sqrtss(4, 4)
    machine.store_stack_ss(4, scratch + 24)
    _store_result(machine, layout, "polar.magnitude", 4)

    machine.x87_fld_rip("polar_cartesian_im")
    machine.x87_fld_rip("polar_cartesian_re")
    machine.x87_fpatan()
    machine.x87_fstp_stack(scratch + 28)
    machine.load_stack_ss(0, scratch + 28)
    machine.loadss(1, "tau")
    machine.divss(0, 1)
    machine.store_stack_ss(0, scratch + 32)
    _store_result(machine, layout, "polar.phase_turns")

    machine.load_stack_ss(0, scratch + 32)
    machine.loadss(1, "tau")
    machine.mulss(0, 1)
    machine.store_stack_ss(0, scratch + 36)
    machine.x87_fld_stack(scratch + 36)
    machine.x87_fcos()
    machine.x87_fstp_stack(scratch + 40)
    machine.x87_fld_stack(scratch + 36)
    machine.x87_fsin()
    machine.x87_fstp_stack(scratch + 44)
    machine.load_stack_ss(0, scratch + 40)
    machine.load_stack_ss(1, scratch + 44)
    machine.load_stack_ss(2, scratch + 24)
    machine.mulss(0, 2)
    machine.mulss(1, 2)
    _store_result(machine, layout, "polar.round_trip_re")
    _store_result(machine, layout, "polar.round_trip_im", 1)

    projective = corpus["projective"]
    real_scale = projective["equivalent_real_scale_cp2"]
    _emit_projective_rescaling_error(
        machine, layout, "projective.real_scale",
        real_scale["left"], real_scale["scale"], real_scale["right"], scratch,
    )
    phase_scale = projective["equivalent_phase_scale_cp2"]
    _emit_projective_rescaling_error(
        machine, layout, "projective.phase_scale",
        phase_scale["left"], phase_scale["scale"], phase_scale["right"], scratch,
    )
    non_equivalent = projective["non_equivalent_cp2"]
    _emit_projective_wedge_error(
        machine, layout, "projective.non_equivalent",
        non_equivalent["left"], non_equivalent["right"], scratch,
    )

    affine = projective["affine_chart_cp1"]
    embedded = affine["embedded"]
    _register_complex(machine, "affine_first", embedded[0])
    _register_complex(machine, "affine_second", embedded[1])
    _load_complex(machine, "affine_second")
    _load_complex_rhs(machine, "affine_first")
    _complex_divide(machine)
    _store_result(machine, layout, "affine_chart.re")
    _store_result(machine, layout, "affine_chart.im", 1)

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


def _render_coordinate(index: int, count: int, low: float, high: float) -> float:
    return low + (high - low) * (index + 0.5) / count


def build_render_elf(corpus: dict[str, Any]) -> tuple[bytes, bytes]:
    render = corpus["render"]
    width = int(render["width"])
    height = int(render["height"])
    if width <= 0 or height <= 0 or width * height > 4096:
        raise ValueError("headless render dimensions are outside the bounded oracle")
    zeros = render["divisor"]["zeros"]
    poles = render["divisor"]["poles"]
    if not zeros or not poles:
        raise ValueError("render fixture must exercise at least one zero and one pole")

    machine = X86()
    payload_size = width * height * 3
    reserve = ((payload_size + 96 + 15) // 16) * 16
    scratch = payload_size
    machine.sub_rsp(reserve)
    for label, value in {
        "zero": 0.0,
        "one": 1.0,
        "minus_one": -1.0,
        "half_255": 127.5,
        "max_255": 255.0,
    }.items():
        machine.f32_constant(label, value)

    q = render["entire_q"]
    _register_complex(machine, "q_constant", q["constant"])
    _register_complex(machine, "q_linear", q["linear"])
    _register_complex(machine, "q_quadratic", q["quadratic"])
    for index, value in enumerate(zeros):
        _register_complex(machine, f"render_zero_{index}", value)
    for index, value in enumerate(poles):
        _register_complex(machine, f"render_pole_{index}", value)

    exp_spec = corpus["complex"]["exponential"]["implementation"]
    degree = int(exp_spec["degree"])
    maximum_q = float(exp_spec["maximum_input_magnitude"])
    viewport = render["viewport"]
    xs = [
        _render_coordinate(i, width, viewport["left"], viewport["right"])
        for i in range(width)
    ]
    ys = [
        _render_coordinate(j, height, viewport["top"], viewport["bottom"])
        for j in range(height)
    ]
    for index, value in enumerate(xs):
        machine.f32_constant(f"render_x_{index}", value)
    for index, value in enumerate(ys):
        machine.f32_constant(f"render_y_{index}", value)

    # The host checks only the approximation-domain precondition. Candidate
    # field values are still computed by the emitted x86 program.
    q_constant = complex(*q["constant"])
    q_linear = complex(*q["linear"])
    q_quadratic = complex(*q["quadratic"])
    for y in ys:
        for x in xs:
            z = complex(x, y)
            q_value = q_constant + q_linear * z + q_quadratic * z * z
            if abs(q_value) > maximum_q:
                raise ValueError("render q(z) exceeds declared exp approximation domain")

    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    machine.data_bytes("ppm_header", header)

    def clamp_and_store(register: int, displacement: int) -> None:
        machine.loadss(6, "zero")
        machine.maxss(register, 6)
        machine.loadss(6, "max_255")
        machine.minss(register, 6)
        machine.cvttss2si_eax(register)
        machine.store_stack_byte_al(displacement)

    pixel_offset = 0
    for y_index in range(height):
        for x_index in range(width):
            x_label = f"render_x_{x_index}"
            y_label = f"render_y_{y_index}"

            # q(z) = constant + linear*z + quadratic*z^2. This evolving state
            # contains only holomorphic operations.
            machine.loadss(0, x_label)
            machine.loadss(1, y_label)
            machine.loadss(2, x_label)
            machine.loadss(3, y_label)
            _complex_multiply(machine)
            _load_complex_rhs(machine, "q_quadratic")
            _complex_multiply(machine)
            machine.store_stack_ss(0, scratch + 16)
            machine.store_stack_ss(1, scratch + 20)

            machine.loadss(0, x_label)
            machine.loadss(1, y_label)
            _load_complex_rhs(machine, "q_linear")
            _complex_multiply(machine)
            machine.load_stack_ss(2, scratch + 16)
            machine.load_stack_ss(3, scratch + 20)
            machine.addss(0, 2)
            machine.addss(1, 3)
            _add_complex_constant(machine, "q_constant")
            machine.store_stack_ss(0, scratch + 24)
            machine.store_stack_ss(1, scratch + 28)

            # exp(q) is the bounded holomorphic degree-7 approximation.
            machine.load_stack_ss(2, scratch + 24)
            machine.load_stack_ss(3, scratch + 28)
            coefficients = [1.0 / math.factorial(k) for k in range(degree, -1, -1)]
            for index, coefficient in enumerate(coefficients):
                machine.f32_constant(
                    f"render_exp_coefficient_{degree}_{index}", coefficient
                )
            machine.loadss(0, f"render_exp_coefficient_{degree}_0")
            machine.loadss(1, "zero")
            for index in range(1, len(coefficients)):
                _complex_multiply(machine)
                machine.loadss(4, f"render_exp_coefficient_{degree}_{index}")
                machine.addss(0, 4)
            machine.store_stack_ss(0, scratch + 32)
            machine.store_stack_ss(1, scratch + 36)

            # R(z): explicit divisor only. Start at 1, multiply zero factors,
            # divide pole factors. No old lasso/path/disc state is present.
            machine.loadss(0, "one")
            machine.loadss(1, "zero")
            machine.store_stack_ss(0, scratch + 40)
            machine.store_stack_ss(1, scratch + 44)
            for index, _ in enumerate(zeros):
                machine.loadss(0, x_label)
                machine.loadss(1, y_label)
                _load_complex_rhs(machine, f"render_zero_{index}")
                machine.subss(0, 2)
                machine.subss(1, 3)
                machine.movss(2, 0)
                machine.movss(3, 1)
                machine.load_stack_ss(0, scratch + 40)
                machine.load_stack_ss(1, scratch + 44)
                _complex_multiply(machine)
                machine.store_stack_ss(0, scratch + 40)
                machine.store_stack_ss(1, scratch + 44)
            for index, _ in enumerate(poles):
                machine.loadss(2, x_label)
                machine.loadss(3, y_label)
                machine.loadss(4, f"render_pole_{index}_re")
                machine.subss(2, 4)
                machine.loadss(4, f"render_pole_{index}_im")
                machine.subss(3, 4)
                machine.load_stack_ss(0, scratch + 40)
                machine.load_stack_ss(1, scratch + 44)
                _complex_divide(machine)
                machine.store_stack_ss(0, scratch + 40)
                machine.store_stack_ss(1, scratch + 44)

            # f = R*H.
            machine.load_stack_ss(0, scratch + 40)
            machine.load_stack_ss(1, scratch + 44)
            machine.load_stack_ss(2, scratch + 32)
            machine.load_stack_ss(3, scratch + 36)
            _complex_multiply(machine)

            # Observation/rendering begins here. Magnitude does not feed back
            # into q, exp(q), R, or f.
            machine.movss(4, 0)
            machine.mulss(4, 0)
            machine.movss(5, 1)
            machine.mulss(5, 1)
            machine.addss(4, 5)
            machine.sqrtss(4, 4)
            machine.movss(5, 4)
            machine.loadss(6, "one")
            machine.addss(5, 6)
            machine.divss(0, 5)
            machine.divss(1, 5)
            machine.divss(4, 5)
            machine.loadss(6, "one")
            machine.addss(0, 6)
            machine.loadss(6, "half_255")
            machine.mulss(0, 6)
            machine.loadss(6, "one")
            machine.addss(1, 6)
            machine.loadss(6, "half_255")
            machine.mulss(1, 6)
            machine.loadss(6, "max_255")
            machine.mulss(4, 6)
            clamp_and_store(0, pixel_offset)
            clamp_and_store(1, pixel_offset + 1)
            clamp_and_store(4, pixel_offset + 2)
            pixel_offset += 3

    machine.mov_eax(1)
    machine.mov_edi(1)
    machine.lea_rsi_rip("ppm_header")
    machine.mov_edx(len(header))
    machine.syscall()
    machine.mov_eax(1)
    machine.mov_edi(1)
    machine.rsi_from_rsp()
    machine.mov_edx(payload_size)
    machine.syscall()
    machine.add_rsp(reserve)
    machine.mov_eax(60)
    machine.mov_edi(0)
    machine.syscall()
    return write_elf(machine.finish()), header


def exp_error_bound(
    value: list[float], degree: int, epsilon: float = F32_EPSILON
) -> float:
    q_abs = abs(complex(*value))
    truncation = (
        math.exp(q_abs)
        * q_abs ** (degree + 1)
        / math.factorial(degree + 1)
    )
    rounding = 64.0 * epsilon * math.exp(q_abs)
    return truncation + rounding


def floating_error_bound(
    expected: complex | float,
    operations: int = 32,
    epsilon: float = F32_EPSILON,
) -> float:
    magnitude = abs(expected)
    return operations * epsilon * max(1.0, magnitude)
