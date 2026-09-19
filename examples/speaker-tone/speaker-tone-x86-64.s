.section .text
.global _start
.type _start, @function

.equ SYS_write,   1
.equ SYS_close,   3
.equ SYS_ioctl,  16
.equ SYS_exit,   60
.equ SYS_openat, 257

.equ AT_FDCWD, -100
.equ O_WRONLY, 1

.equ SNDCTL_DSP_SYNC,     0x00005001
.equ SNDCTL_DSP_SPEED,    0xc0045002
.equ SNDCTL_DSP_SETFMT,   0xc0045005
.equ SNDCTL_DSP_CHANNELS, 0xc0045006
.equ AFMT_U8, 8

.equ SAMPLE_RATE, 8000
.equ SAMPLE_COUNT, 2000
.equ CYCLES, 100
.equ HALF_PERIOD, 10

_start:
        # openat(AT_FDCWD, "/dev/dsp", O_WRONLY, 0)
        mov     $SYS_openat, %eax
        mov     $AT_FDCWD, %rdi
        lea     dsp_path(%rip), %rsi
        mov     $O_WRONLY, %edx
        xor     %r10d, %r10d
        syscall
        test    %rax, %rax
        js      fail_open
        mov     %rax, %r12

        # Request unsigned 8-bit PCM.
        movl    $AFMT_U8, pcm_format(%rip)
        mov     $SYS_ioctl, %eax
        mov     %r12, %rdi
        mov     $SNDCTL_DSP_SETFMT, %esi
        lea     pcm_format(%rip), %rdx
        syscall
        test    %rax, %rax
        js      fail_format
        cmpl    $AFMT_U8, pcm_format(%rip)
        jne     fail_format

        # Request one output channel.
        movl    $1, pcm_channels(%rip)
        mov     $SYS_ioctl, %eax
        mov     %r12, %rdi
        mov     $SNDCTL_DSP_CHANNELS, %esi
        lea     pcm_channels(%rip), %rdx
        syscall
        test    %rax, %rax
        js      fail_channels
        cmpl    $1, pcm_channels(%rip)
        jne     fail_channels

        # Request an 8 kHz sample rate.
        movl    $SAMPLE_RATE, pcm_rate(%rip)
        mov     $SYS_ioctl, %eax
        mov     %r12, %rdi
        mov     $SNDCTL_DSP_SPEED, %esi
        lea     pcm_rate(%rip), %rdx
        syscall
        test    %rax, %rax
        js      fail_rate

        # Accept a device-adjusted rate only when it stays close enough to
        # preserve the intended 400 Hz tone fixture.
        mov     pcm_rate(%rip), %eax
        cmp     $7600, %eax
        jl      fail_rate
        cmp     $8400, %eax
        jg      fail_rate

        # 100 cycles * 20 samples/cycle at 8 kHz = 0.25 s at exactly 400 Hz.
        lea     tone_buffer(%rip), %rdi
        mov     $CYCLES, %ecx
fill_cycle:
        mov     $HALF_PERIOD, %r8d
fill_high:
        movb    $224, (%rdi)
        inc     %rdi
        dec     %r8d
        jne     fill_high

        mov     $HALF_PERIOD, %r8d
fill_low:
        movb    $32, (%rdi)
        inc     %rdi
        dec     %r8d
        jne     fill_low

        dec     %ecx
        jne     fill_cycle

        lea     tone_buffer(%rip), %r13
        mov     $SAMPLE_COUNT, %r14
write_more:
        mov     $SYS_write, %eax
        mov     %r12, %rdi
        mov     %r13, %rsi
        mov     %r14, %rdx
        syscall
        test    %rax, %rax
        jle     fail_write
        add     %rax, %r13
        sub     %rax, %r14
        jne     write_more

        # Wait until the OSS playback queue drains.
        mov     $SYS_ioctl, %eax
        mov     %r12, %rdi
        mov     $SNDCTL_DSP_SYNC, %esi
        xor     %edx, %edx
        syscall
        test    %rax, %rax
        js      fail_sync

        mov     $SYS_close, %eax
        mov     %r12, %rdi
        syscall

        xor     %edi, %edi
        jmp     exit

fail_open:
        mov     $10, %edi
        jmp     exit
fail_format:
        mov     $11, %edi
        jmp     exit
fail_channels:
        mov     $12, %edi
        jmp     exit
fail_rate:
        mov     $13, %edi
        jmp     exit
fail_write:
        mov     $14, %edi
        jmp     exit
fail_sync:
        mov     $15, %edi

exit:
        mov     $SYS_exit, %eax
        syscall
.size _start, .-_start

.section .rodata
dsp_path:
        .asciz "/dev/dsp"

.section .data
.align 4
pcm_format:
        .long AFMT_U8
pcm_channels:
        .long 1
pcm_rate:
        .long SAMPLE_RATE

.section .bss
.align 16
tone_buffer:
        .skip SAMPLE_COUNT

.section .note.GNU-stack,"",@progbits
