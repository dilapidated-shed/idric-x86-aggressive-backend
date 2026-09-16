#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=${WORK_DIR:-"$script_dir/build"}
cc=${CC:-cc}

rm -rf "$work"
mkdir -p "$work"

for name in gpio_output gpio_input gpio_edge_wait; do
    "$cc" -std=c11 -Wall -Wextra -Werror -O2 \
        -I"$script_dir" "$script_dir/$name.c" -o "$work/$name"
    file "$work/$name" | grep -q 'ELF 64-bit.*x86-64'
    set +e
    "$work/$name" /dev/idric-gpio-does-not-exist 0 >/dev/null 2>&1
    status=$?
    set -e
    [ "$status" -eq 10 ] || {
        printf 'FAIL: %s no-chip status %s, expected 10\n' "$name" "$status" >&2
        exit 1
    }
done

printf '%s\n' \
    'PASS: x86-64 GPIO v2 oracles build as native ELF executables' \
    'PASS: output, input, and edge-wait preserve the explicit no-chip boundary'
