# Speaker tone — x86-64 Linux oracle

This directory advances the `speaker_tone` row in `isomorphisms/Idric#85`.
It is a handwritten Linux/x86-64 platform oracle, not evidence that Idriç
currently emits this program.

The native no-libc ELF opens `/dev/dsp`, asks the Linux OSS PCM compatibility
layer for unsigned 8-bit mono audio near 8 kHz, constructs a 400 Hz square-wave
fixture, writes 0.25 seconds of samples, drains the playback queue, and exits.

The fixture is deliberately exact and small:

- nominal sample rate: 8000 samples/s;
- period: 20 samples;
- nominal frequency: 400 Hz;
- length: 100 cycles / 2000 samples / 0.25 s;
- high sample: 224;
- low sample: 32.

`/dev/dsp` is one Linux adapter below the semantic action “play a tone”. ALSA
OSS emulation exposes `/dev/dsp` through `snd-pcm-oss`; another Linux adapter or
Android implementation may use a different boundary without changing the
fixture. Linux documents `snd-pcm-oss` as the PCM OSS compatibility module.

The ordinary CI check assembles and inspects the ELF. When the hosted runner has
no `/dev/dsp`, it also verifies the program's explicit exit-10 no-device path.
That is not speaker acceptance.

Full-system acceptance must boot an Ubuntu guest with a declared virtual audio
device, execute this same native ELF through the guest audio stack, capture
QEMU's audio output as WAV, and verify frequency and duration from the capture.
A generated PCM buffer without device playback is only a lower-level fixture.
