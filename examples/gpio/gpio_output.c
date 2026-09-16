#include "gpio_common.h"

static int set_value(int line_fd, uint64_t bit)
{
    struct gpio_v2_line_values values;

    memset(&values, 0, sizeof(values));
    values.mask = 1;
    values.bits = bit ? 1 : 0;
    return ioctl(line_fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &values);
}

int main(int argc, char **argv)
{
    unsigned int offset;
    int chip_fd;
    int line_fd;

    if (argc != 3 || parse_offset(argv[2], &offset) != 0)
        return 64;

    line_fd = request_one_line(argv[1], offset, GPIO_V2_LINE_FLAG_OUTPUT,
                               &chip_fd);
    if (line_fd < 0)
        return -line_fd;

    if (set_value(line_fd, 1) < 0)
        return 12;
    puts("HIGH");
    fflush(stdout);
    sleep(1);

    if (set_value(line_fd, 0) < 0)
        return 12;
    puts("LOW");
    fflush(stdout);
    sleep(1);

    close(line_fd);
    close(chip_fd);
    return 0;
}
