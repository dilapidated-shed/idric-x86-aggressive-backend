#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
work=${WORK_DIR:-"$repo_root/build/full-system-x86-accelerometer-probe"}
rootfs="$work/rootfs"
disk="$work/ubuntu-x86-64.raw"
serial="$work/serial.log"
kernel="$work/vmlinuz"
initrd="$work/initrd.img"

rm -rf "$work"
mkdir -p "$work"

sudo debootstrap \
    --variant=minbase \
    --components=main,universe \
    --include=linux-image-generic,kmod,busybox-static,initramfs-tools \
    noble "$rootfs" http://archive.ubuntu.com/ubuntu

sudo tee "$rootfs/usr/local/sbin/device-action-init" >/dev/null <<'GUEST_INIT'
#!/bin/busybox sh
set -eu

exec </dev/console >/dev/console 2>&1
/bin/busybox mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
/bin/busybox mount -t proc proc /proc 2>/dev/null || true
/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null || true
mkdir -p /sys/kernel/config
/bin/busybox mount -t configfs configfs /sys/kernel/config 2>/dev/null || true

echo '=== IIO module probes ==='
for module in industrialio industrialio-configfs industrialio-sw-device industrialio-sw-trigger industrialio-triggered-buffer iio-trig-hrtimer iio_dummy; do
    if /sbin/modprobe "$module" 2>/dev/null; then
        echo "MODULE_OK=$module"
    else
        echo "MODULE_MISSING=$module"
    fi
done

echo '=== IIO configfs ==='
find /sys/kernel/config/iio -maxdepth 4 -type d -print 2>/dev/null || true

if [ ! -d /sys/kernel/config/iio/devices/dummy ]; then
    echo 'IIO_DUMMY_CONFIGFS=0'
    /bin/busybox poweroff -f
    /bin/busybox sleep 5
    exit 20
fi

echo 'IIO_DUMMY_CONFIGFS=1'
mkdir /sys/kernel/config/iio/devices/dummy/idric-accel

i=0
device=
while [ "$i" -lt 50 ]; do
    for candidate in /sys/bus/iio/devices/iio:device*; do
        [ -e "$candidate/name" ] || continue
        if [ "$(cat "$candidate/name")" = idric-accel ]; then
            device=$candidate
            break
        fi
    done
    [ -n "$device" ] && break
    /bin/busybox sleep 0.1
    i=$((i + 1))
done

[ -n "$device" ] || {
    echo 'IIO_DUMMY_DEVICE=0'
    /bin/busybox poweroff -f
    /bin/busybox sleep 5
    exit 21
}
echo "IIO_DUMMY_DEVICE=$device"

echo '=== direct accelerometer ==='
for attr in in_accel_x_raw in_accel_x_calibbias in_accel_x_calibscale sampling_frequency; do
    if [ -r "$device/$attr" ]; then
        printf '%s=' "$attr"
        cat "$device/$attr"
    else
        echo "MISSING_ATTR=$attr"
    fi
done

echo '=== scan elements ==='
find "$device/scan_elements" -maxdepth 1 -type f -print -exec sh -c 'printf "  "; cat "$1"' _ {} \; 2>/dev/null || true

echo '=== buffer ==='
find "$device/buffer" -maxdepth 1 -type f -print -exec sh -c 'printf "  "; cat "$1" 2>/dev/null || true' _ {} \; 2>/dev/null || true

if [ -e "$device/scan_elements/in_accel_x_en" ] && [ -e "$device/scan_elements/in_timestamp_en" ] && [ -e "$device/buffer/enable" ]; then
    echo 'IIO_BUFFER_ACCEL_TIMESTAMP=1'
else
    echo 'IIO_BUFFER_ACCEL_TIMESTAMP=0'
fi

if [ -d /sys/kernel/config/iio/triggers/hrtimer ]; then
    mkdir /sys/kernel/config/iio/triggers/hrtimer/idric-accel-trigger
    echo 'IIO_HRTIMER_CONFIGFS=1'
    for trigger in /sys/bus/iio/devices/trigger*; do
        [ -e "$trigger/name" ] || continue
        printf 'TRIGGER=%s:' "$trigger"
        cat "$trigger/name"
    done
else
    echo 'IIO_HRTIMER_CONFIGFS=0'
fi

echo 'IIO_ACCEL_PROBE_COMPLETE=1'
/bin/busybox sync
/bin/busybox poweroff -f
/bin/busybox sleep 5
GUEST_INIT
sudo chmod 0755 "$rootfs/usr/local/sbin/device-action-init"

kernel_source=$(find "$rootfs/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort | tail -n 1)
initrd_source=$(find "$rootfs/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort | tail -n 1)
[ -n "$kernel_source" ] && [ -n "$initrd_source" ]
sudo cp "$kernel_source" "$kernel"
sudo cp "$initrd_source" "$initrd"
sudo chown "$(id -u):$(id -g)" "$kernel" "$initrd"

truncate -s 2G "$disk"
sudo mkfs.ext4 -q -d "$rootfs" "$disk"
sudo chown "$(id -u):$(id -g)" "$disk"
rm -f "$serial"

qemu-system-x86_64 \
    -machine pc,accel=tcg -cpu qemu64 -m 512M \
    -kernel "$kernel" -initrd "$initrd" \
    -append 'console=ttyS0,115200 root=/dev/vda rw init=/usr/local/sbin/device-action-init panic=-1' \
    -drive "file=$disk,format=raw,if=virtio" \
    -display none -serial "file:$serial" -no-reboot &
qemu_pid=$!

cleanup() {
    if kill -0 "$qemu_pid" 2>/dev/null; then
        kill "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT HUP INT TERM

i=0
while [ "$i" -lt 180 ]; do
    if [ -f "$serial" ] && grep -q 'IIO_ACCEL_PROBE_COMPLETE=1' "$serial"; then break; fi
    if ! kill -0 "$qemu_pid" 2>/dev/null; then break; fi
    sleep 1
    i=$((i + 1))
done
cleanup
trap - EXIT HUP INT TERM
cat "$serial" 2>/dev/null || true
grep -q 'IIO_ACCEL_PROBE_COMPLETE=1' "$serial"
