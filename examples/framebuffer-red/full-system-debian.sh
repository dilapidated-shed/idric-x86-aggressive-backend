#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

DEBIAN_SUITE=${DEBIAN_SUITE:-trixie}
DEBIAN_MIRROR=${DEBIAN_MIRROR:-https://deb.debian.org/debian}
QEMU=${QEMU:-qemu-system-x86_64}

work=${WORK_DIR:-"$repo_root/build/full-system-x86-red"}
rootfs="$work/rootfs"
disk="$work/debian-x86-64.raw"
serial="$work/serial.log"
monitor="$work/monitor.sock"
screen="$work/red.ppm"
program="$work/framebuffer-red-x86-64.elf"
object="$work/framebuffer-red-x86-64.o"
kernel="$work/vmlinuz"
initrd="$work/initrd.img"

rm -rf "$work"
mkdir -p "$work"

for command in debootstrap mkfs.ext4 python3 "$QEMU" as ld; do
    command -v "$command" >/dev/null 2>&1 || {
        printf 'FAIL: required command not found: %s\n' "$command" >&2
        exit 1
    }
done

as --64 -o "$object" "$script_dir/framebuffer-red-x86-64.s"
ld -m elf_x86_64 -nostdlib --build-id=none -s \
    -T "$script_dir/framebuffer-red-x86-64.ld" \
    -o "$program" "$object"

sudo debootstrap \
    --variant=minbase \
    --include=linux-image-amd64,kmod,busybox \
    "$DEBIAN_SUITE" "$rootfs" "$DEBIAN_MIRROR"

sudo install -m 0755 "$program" "$rootfs/usr/local/bin/screen-red"

sudo tee "$rootfs/usr/local/sbin/device-action-init" >/dev/null <<'GUEST_INIT'
#!/bin/busybox sh

exec </dev/console >/dev/console 2>&1

/bin/busybox mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
/bin/busybox mount -t proc proc /proc 2>/dev/null || true
/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null || true

for module in bochs bochs_drm simpledrm vesafb; do
    /sbin/modprobe "$module" 2>/dev/null || true
done

i=0
while [ ! -e /dev/fb0 ] && [ "$i" -lt 20 ]; do
    /bin/busybox sleep 1
    i=$((i + 1))
done

if [ ! -e /dev/fb0 ]; then
    echo 'FBDEV_PRESENT=0'
    echo 'PROGRAM_STATUS=125'
    /bin/busybox poweroff -f
    /bin/busybox sleep 5
    exit 125
fi

echo 'FBDEV_PRESENT=1'
echo 'SCREEN_RED_RUNNING=1'
/usr/local/bin/screen-red
status=$?
echo "PROGRAM_STATUS=$status"
/bin/busybox sync
/bin/busybox poweroff -f
/bin/busybox sleep 5
exit "$status"
GUEST_INIT
sudo chmod 0755 "$rootfs/usr/local/sbin/device-action-init"

kernel_source=$(find "$rootfs/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort | tail -n 1)
initrd_source=$(find "$rootfs/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort | tail -n 1)

[ -n "$kernel_source" ] && [ -n "$initrd_source" ] || {
    printf '%s\n' 'FAIL: Debian rootfs did not install a kernel and initrd' >&2
    exit 1
}

sudo cp "$kernel_source" "$kernel"
sudo cp "$initrd_source" "$initrd"
sudo chown "$(id -u):$(id -g)" "$kernel" "$initrd"

truncate -s 1G "$disk"
sudo mkfs.ext4 -q -d "$rootfs" "$disk"
sudo chown "$(id -u):$(id -g)" "$disk"

rm -f "$serial" "$monitor" "$screen"

"$QEMU" \
    -machine pc,accel=tcg \
    -cpu qemu64 \
    -m 512M \
    -kernel "$kernel" \
    -initrd "$initrd" \
    -append 'console=ttyS0,115200 root=/dev/vda rw init=/usr/local/sbin/device-action-init panic=-1' \
    -drive "file=$disk,format=raw,if=virtio" \
    -vga std \
    -display none \
    -serial "file:$serial" \
    -monitor "unix:$monitor,server=on,wait=off" \
    -no-reboot &
qemu_pid=$!

cleanup_qemu() {
    if kill -0 "$qemu_pid" 2>/dev/null; then
        kill "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
}
trap cleanup_qemu EXIT HUP INT TERM

i=0
while [ "$i" -lt 120 ]; do
    if [ -f "$serial" ] && grep -q 'SCREEN_RED_RUNNING=1' "$serial"; then
        break
    fi
    if ! kill -0 "$qemu_pid" 2>/dev/null; then
        break
    fi
    sleep 1
    i=$((i + 1))
done

if ! [ -f "$serial" ] || ! grep -q 'SCREEN_RED_RUNNING=1' "$serial"; then
    cat "$serial" 2>/dev/null || true
    printf '%s\n' 'FAIL: guest never reached red-screen execution' >&2
    exit 1
fi

sleep 1

python3 - "$monitor" "$screen" <<'PY'
import socket
import sys
import time

monitor, output = sys.argv[1:]
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
for _ in range(50):
    try:
        sock.connect(monitor)
        break
    except (FileNotFoundError, ConnectionRefusedError):
        time.sleep(0.1)
else:
    raise SystemExit("FAIL: QEMU monitor socket was unavailable")

sock.settimeout(2)
try:
    sock.recv(65536)
except TimeoutError:
    pass
sock.sendall(("screendump " + output + "\n").encode())
time.sleep(0.5)
try:
    sock.recv(65536)
except TimeoutError:
    pass
sock.close()
PY

i=0
while kill -0 "$qemu_pid" 2>/dev/null && [ "$i" -lt 30 ]; do
    sleep 1
    i=$((i + 1))
done
cleanup_qemu
trap - EXIT HUP INT TERM

cat "$serial"

grep -q 'FBDEV_PRESENT=1' "$serial"
grep -q 'PROGRAM_STATUS=0' "$serial"

python3 - "$screen" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
data = path.read_bytes()
if not data.startswith(b"P6"):
    raise SystemExit("FAIL: QEMU screendump is not binary PPM")

pos = 2
tokens = []
while len(tokens) < 3:
    while pos < len(data) and data[pos] in b" \t\r\n":
        pos += 1
    if pos < len(data) and data[pos] == ord("#"):
        pos = data.index(b"\n", pos) + 1
        continue
    end = pos
    while end < len(data) and data[end] not in b" \t\r\n":
        end += 1
    tokens.append(data[pos:end])
    pos = end

width, height, maximum = map(int, tokens)
while pos < len(data) and data[pos] in b" \t\r\n":
    pos += 1
pixels = data[pos:]
if maximum != 255 or len(pixels) != width * height * 3:
    raise SystemExit("FAIL: unexpected PPM geometry or sample depth")

red = 0
count = width * height
for i in range(0, len(pixels), 3):
    r, g, b = pixels[i:i + 3]
    if r >= 224 and g <= 32 and b <= 32:
        red += 1

ratio = red / count
print(f"presented_red_pixels={red}/{count} ({ratio:.6f})")
if ratio < 0.98:
    raise SystemExit("FAIL: captured guest display is not overwhelmingly red")
PY

printf '%s\n' \
    'PASS: native x86-64 ELF executed inside a full-system Debian guest' \
    'PASS: guest used /dev/fb0 and returned status 0' \
    'PASS: QEMU presented-output capture is overwhelmingly red'
