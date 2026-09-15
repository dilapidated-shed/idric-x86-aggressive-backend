#!/usr/bin/env bash
set -Eeuo pipefail

artifact_root=${1:?usage: run_complex_projective_thin_debian.sh ARTIFACT_DIR}
artifact_root=$(cd "$artifact_root" && pwd)

for executable in \
  complex-corpus.elf \
  complex-projective-contract.elf \
  complex-render.elf
do
  if [[ ! -x "$artifact_root/$executable" ]]; then
    echo "missing executable artifact: $artifact_root/$executable" >&2
    exit 1
  fi
done

docker run --rm \
  -v "$artifact_root:/work:ro" \
  debian:13-slim \
  /work/complex-corpus.elf > "$artifact_root/thin-debian-complex-corpus.bin"

cmp "$artifact_root/complex-corpus.bin" \
    "$artifact_root/thin-debian-complex-corpus.bin"

docker run --rm \
  -v "$artifact_root:/work:ro" \
  debian:13-slim \
  /work/complex-projective-contract.elf \
  > "$artifact_root/thin-debian-complex-projective-contract.bin"

cmp "$artifact_root/complex-projective-contract.bin" \
    "$artifact_root/thin-debian-complex-projective-contract.bin"

docker run --rm \
  -v "$artifact_root:/work:ro" \
  debian:13-slim \
  /work/complex-render.elf \
  > "$artifact_root/thin-debian-complex-projective-scene.ppm"

cmp "$artifact_root/complex-projective-scene.ppm" \
    "$artifact_root/thin-debian-complex-projective-scene.ppm"

{
  printf 'THIN_DEBIAN_COMPLEX_PROJECTIVE\t2\n'
  printf 'image\tdebian:13-slim\n'
  printf 'stage\tcomplex_arithmetic\tPASS\n'
  printf 'stage\tprojective_contract\tPASS\n'
  printf 'stage\theadless_render\tPASS\n'
  printf 'comparison\tbyte_identical_to_github_hosted_ubuntu_x86\tPASS\n'
} > "$artifact_root/thin-debian-receipt.tsv"

{
  printf 'thin_runtime_image\tdebian:13-slim\n'
  printf 'stage\tthin_debian_execution\tPASS\n'
  printf 'stage\tthin_runtime_execution\tPASS\n'
} >> "$artifact_root/acceptance-receipt.tsv"

cat "$artifact_root/thin-debian-receipt.tsv"
cat "$artifact_root/acceptance-receipt.tsv"
