#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

UBUNTU_SUITE=${UBUNTU_SUITE:-noble}
UBUNTU_MIRROR=${UBUNTU_MIRROR:-http://archive.ubuntu.com/ubuntu}
QEMU=${QEMU:-qemu-system-x86_64}
CC=${CC:-cc}

work=${WORK_DIR:-"$repo_root/build/full-system-x86-gpio"}
rootfs="$work/rootfs"
disk="$work/ubuntu-x86-64.raw"
serial="$work/serial.log"
kernel="$work/vmlinuz"
initrd="$work/initrd.img"
programs="$work/programs"

rm -rf "$work"
mkdir -p "$work" "$programs"

for command in debootstrap mkfs.ext4 "$QEMU" "$CC"; do
    command -v "$command" >/dev/null 2>&1 || {
        printf 'FAIL: required command not found: %s\n' "$command" >&2
        exit 1
    }
done

for name in gpio_output gpio_input gpio_edge_wait; do
    "$CC" -std=c11 -Wall -Wextra -Werror -O2 \
        -I"$script_dir" "$script_dir/$name.c" -o "$programs/$name"
done

sudo debootstrap \
    --variant=minbase \
    --components=main,universe \
    --include=linux-image-generic,kmod,busybox-static,initramfs-tools \
    "$UBUNTU_SUITE" "$rootfs" "$UBUNTU_MIRROR"

for name in gpio_output gpio_input gpio_edge_wait; do
    sudo install -m 0755 "$programs/$name" "$rootfs/usr/local/bin/$name"
done

sudo tee "$rootfs/usr/local/sbin/device-action-init" >/dev/null <<'GUEST_INIT'
#!/bin/busybox sh
set -eu

exec </dev/console >/dev/console 2>&1

/bin/busybox mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
/bin/busybox mount -t proc proc /proc 2>/dev/null || true
/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null || true
mkdir -p /sys/kernel/config
/bin/busybox mount -t configfs configfs /sys/kernel/config 2>/dev/null || true

/sbin/modprobe gpio-sim

config=/sys/kernel/config/gpio-sim/idric-device
bank="$config/gpio-bank0"
line="$bank/line0"
mkdir -p "$line"
echo 1 > "$bank/num_lines"
echo idric-gpio-line-0 > "$line/name"
echo 1 > "$config/live"

chip_name=$(cat "$bank/chip_name")
dev_name=$(cat "$config/dev_name")
chip="/dev/$chip_name"
line_state=$(find "/sys/devices/platform/$dev_name" -type d -name sim_gpio0 | head -n 1)

[ -c "$chip" ] || {
    echo "GPIO_CHIP_MISSING=$chip"
    exit 120
}
[ -n "$line_state" ] || {
    echo 'GPIO_SIM_LINE_STATE_MISSING=1'
    exit 121
}

echo "GPIO_CHIP=$chip"
echo "GPIO_SIM_DEVICE=$dev_name"

output_log=/tmp/gpio-output.log
/usr/local/bin/gpio_output "$chip" 0 >"$output_log" &
output_pid=$!

i=0
while ! grep -q '^HIGH$' "$output_log" 2>/dev/null && [ "$i" -lt 50 ]; do
    /bin/busybox sleep 0.02
    i=$((i + 1))
done
high=$(cat "$line_state/value")

i=0
while ! grep -q '^LOW$' "$output_log" 2>/dev/null && [ "$i" -lt 100 ]; do
    /bin/busybox sleep 0.02
    i=$((i + 1))
done
low=$(cat "$line_state/value")
wait "$output_pid"
cat "$output_log"
echo "GPIO_OUTPUT_OBSERVED=$high,$low"
[ "$high" = 1 ] && [ "$low" = 0 ]

echo pull-down > "$line_state/pull"
input_low=$(/usr/local/bin/gpio_input "$chip" 0)
echo pull-up > "$line_state/pull"
input_high=$(/usr/local/bin/gpio_input "$chip" 0)
echo "GPIO_INPUT_OBSERVED=$input_low,$input_high"
[ "$input_low" = 0 ] && [ "$input_high" = 1 ]

echo pull-down > "$line_state/pull"
edge_log=/tmp/gpio-edge.log
/usr/local/bin/gpio_edge_wait "$chip" 0 >"$edge_log" &
edge_pid=$!
/bin/busybox sleep 0.2
echo pull-up > "$line_state/pull"
wait "$edge_pid"
cat "$edge_log"
grep -q '^rising offset=0 ' "$edge_log"
echo 'GPIO_EDGE_OBSERVED=rising'

echo 'GPIO_TESTS_PASS=1'
/bin/busybox sync
/bin/busybox poweroff -f
/bin/busybox sleep 5
GUEST_INIT
sudo chmod 0755 "$rootfs/usr/local/sbin/device-action-init"

kernel_source=$(find "$rootfs/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort | tail -n 1)
initrd_source=$(find "$rootfs/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort | tail -n 1)
[ -n "$kernel_source" ] && [ -n "$initrd_source" ] || {
    printf '%s\n' 'FAIL: Ubuntu rootfs did not install a kernel and initrd' >&2
    exit 1
}

sudo cp "$kernel_source" "$kernel"
sudo cp "$initrd_source" "$initrd"
sudo chown "$(id -u):$(id -g)" "$kernel" "$initrd"

truncate -s 2G "$disk"
sudo mkfs.ext4 -q -d "$rootfs" "$disk"
sudo chown "$(id -u):$(id -g)" "$disk"
rm -f "$serial"

"$QEMU" \
    -machine pc,accel=tcg \
    -cpu qemu64 \
    -m 512M \
    -kernel "$kernel" \
    -initrd "$initrd" \
    -append 'console=ttyS0,115200 root=/dev/vda rw init=/usr/local/sbin/device-action-init panic=-1' \
    -drive "file=$disk,format=raw,if=virtio" \
    -display none \
    -serial "file:$serial" \
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
while [ "$i" -lt 180 ]; do
    if [ -f "$serial" ] && grep -q 'GPIO_TESTS_PASS=1' "$serial"; then
        break
    fi
    if ! kill -0 "$qemu_pid" 2>/dev/null; then
        break
    fi
    sleep 1
    i=$((i + 1))
done

cleanup_qemu
trap - EXIT HUP INT TERM
cat "$serial" 2>/dev/null || true
grep -q 'GPIO_TESTS_PASS=1' "$serial"

echo 'PASS: x86-64 Ubuntu guest exercised gpio_output, gpio_input, and gpio_edge_wait through gpio-sim'
