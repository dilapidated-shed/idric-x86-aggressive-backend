#ifndef IDRIC_GPIO_COMMON_H
#define IDRIC_GPIO_COMMON_H

#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static int parse_offset(const char *text, unsigned int *offset)
{
    char *end = NULL;
    unsigned long value;

    errno = 0;
    value = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value > UINT32_MAX)
        return -1;

    *offset = (unsigned int)value;
    return 0;
}

static int request_one_line(const char *chip_path, unsigned int offset,
                            uint64_t flags, int *chip_fd_out)
{
    struct gpio_v2_line_request request;
    int chip_fd;

    chip_fd = open(chip_path, O_RDONLY);
    if (chip_fd < 0)
        return -10;

    memset(&request, 0, sizeof(request));
    request.offsets[0] = offset;
    memcpy(request.consumer, "idric-device-oracle", 19);
    request.config.flags = flags;
    request.num_lines = 1;

    if (ioctl(chip_fd, GPIO_V2_GET_LINE_IOCTL, &request) < 0) {
        close(chip_fd);
        return -11;
    }

    *chip_fd_out = chip_fd;
    return request.fd;
}

#endif
