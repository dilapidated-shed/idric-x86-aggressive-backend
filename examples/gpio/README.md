# GPIO device-action oracles

These are handwritten native Linux platform oracles for the device-action matrix. They use the current GPIO character-device v2 ABI directly through `/dev/gpiochipN`.

- `gpio_output` requests one line as output, drives it high, then low.
- `gpio_input` requests one line as input and prints one logical value.
- `gpio_edge_wait` requests rising-edge detection and blocks until one event arrives.

The full-system acceptance lane uses the kernel `gpio-sim` provider. The programs still talk only to the ordinary GPIO character device; the harness uses gpio-sim's independent sysfs `pull` and `value` controls to inject and observe line state.

A successful simulated-device receipt is Linux platform evidence. It is not compiler-generated Idriç evidence and is not physical GPIO evidence.
