#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

AS=${AS:-as}
LD=${LD:-ld}
FILE=${FILE:-file}
READ_ELF=${READ_ELF:-readelf}

out_dir=${OUT_DIR:-"$repo_root/build/speaker-tone"}
object="$out_dir/speaker-tone-x86-64.o"
program="$out_dir/speaker-tone-x86-64.elf"

mkdir -p "$out_dir"

"$AS" --64 -o "$object" "$script_dir/speaker-tone-x86-64.s"
"$LD" -m elf_x86_64 -nostdlib --build-id=none -s -e _start \
    -o "$program" "$object"

"$FILE" "$program" | grep -q 'ELF 64-bit.*x86-64'
"$READ_ELF" -h "$program" | grep -q 'Class:.*ELF64'
"$READ_ELF" -h "$program" | grep -q 'Machine:.*Advanced Micro Devices X86-64'
if "$READ_ELF" -l "$program" | grep -q 'INTERP'; then
    printf '%s\n' 'FAIL: speaker-tone reference unexpectedly has PT_INTERP' >&2
    exit 1
fi

if [ ! -e /dev/dsp ]; then
    set +e
    "$program"
    status=$?
    set -e
    if [ "$status" -ne 10 ]; then
        printf 'FAIL: expected no-/dev/dsp exit 10, got %s\n' "$status" >&2
        exit 1
    fi
    printf '%s\n' 'PASS: hosted Linux exercised the explicit no-/dev/dsp path (exit 10)'
else
    printf '%s\n' 'SKIP: host has /dev/dsp; device playback belongs to the full-system receipt'
fi

printf '%s\n' \
    'PASS: x86-64 speaker-tone oracle assembled, linked, and inspected' \
    'PENDING: full-system virtual audio playback and WAV capture'
