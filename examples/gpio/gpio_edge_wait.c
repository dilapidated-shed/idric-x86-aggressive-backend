#include "gpio_common.h"

int main(int argc, char **argv)
{
    struct gpio_v2_line_event event;
    unsigned int offset;
    ssize_t count;
    int chip_fd;
    int line_fd;

    if (argc != 3 || parse_offset(argv[2], &offset) != 0)
        return 64;

    line_fd = request_one_line(argv[1], offset,
                               GPIO_V2_LINE_FLAG_INPUT |
                                   GPIO_V2_LINE_FLAG_EDGE_RISING,
                               &chip_fd);
    if (line_fd < 0)
        return -line_fd;

    do {
        count = read(line_fd, &event, sizeof(event));
    } while (count < 0 && errno == EINTR);

    if (count != (ssize_t)sizeof(event))
        return 12;
    if (event.id != GPIO_V2_LINE_EVENT_RISING_EDGE || event.offset != offset)
        return 13;

    printf("rising offset=%u seq=%u line_seq=%u\n", event.offset,
           event.seqno, event.line_seqno);
    close(line_fd);
    close(chip_fd);
    return 0;
}
