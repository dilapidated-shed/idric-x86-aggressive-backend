#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

AS=${AS:-as}
LD=${LD:-ld}
FILE=${FILE:-file}
READ_ELF=${READ_ELF:-readelf}

out_dir=${OUT_DIR:-"$repo_root/build/framebuffer-red"}
object="$out_dir/framebuffer-red-x86-64.o"
program="$out_dir/framebuffer-red-x86-64.elf"

mkdir -p "$out_dir"

"$AS" --64 -o "$object" "$script_dir/framebuffer-red-x86-64.s"
"$LD" -m elf_x86_64 -nostdlib --build-id=none -s \
  -T "$script_dir/framebuffer-red-x86-64.ld" \
  -o "$program" "$object"

"$FILE" "$program" | grep -q 'ELF 64-bit.*x86-64'
"$READ_ELF" -h "$program" | grep -q 'Class:.*ELF64'
"$READ_ELF" -h "$program" | grep -q 'Machine:.*Advanced Micro Devices X86-64'
if "$READ_ELF" -l "$program" | grep -q 'INTERP'; then
  printf '%s\n' 'FAIL: framebuffer reference unexpectedly has PT_INTERP' >&2
  exit 1
fi

set +e
"$program"
status=$?
set -e

if [ "$status" -ne 10 ]; then
  printf 'FAIL: expected no-framebuffer exit 10 on hosted Ubuntu, got %s\n' "$status" >&2
  exit 1
fi

printf '%s\n' \
  'PASS: x86-64 framebuffer-red reference assembled, linked, and inspected' \
  'PASS: hosted Ubuntu executed the expected no-framebuffer path (exit 10)' \
  'PENDING: full-system guest display execution and presented-output capture'
