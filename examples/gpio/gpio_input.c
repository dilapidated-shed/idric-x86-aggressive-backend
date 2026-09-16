#include "gpio_common.h"

int main(int argc, char **argv)
{
    struct gpio_v2_line_values values;
    unsigned int offset;
    int chip_fd;
    int line_fd;

    if (argc != 3 || parse_offset(argv[2], &offset) != 0)
        return 64;

    line_fd = request_one_line(argv[1], offset, GPIO_V2_LINE_FLAG_INPUT,
                               &chip_fd);
    if (line_fd < 0)
        return -line_fd;

    memset(&values, 0, sizeof(values));
    values.mask = 1;
    if (ioctl(line_fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &values) < 0)
        return 12;

    printf("%u\n", (unsigned int)(values.bits & 1));
    close(line_fd);
    close(chip_fd);
    return 0;
}
