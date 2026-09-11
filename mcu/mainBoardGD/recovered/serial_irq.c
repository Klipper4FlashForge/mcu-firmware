/* Generic serial interrupt buffers, kept in a separate translation unit as in
 * Klipper's src/generic/serial_irq.c. The port IRQ calls these out of line. */
#include "serial.h"

int serial_get_tx_byte(uint8_t *pdata)
{
    if (transmit_pos >= transmit_max)
        return -1;
    /* Capture this byte's address before advancing the shared position. Stock
     * 0x458a stores the new position before 0x458c reads the buffered byte. */
    uint8_t *next = &transmit_buf[transmit_pos];
    transmit_pos++;
    *pdata = *next;
    return 0;
}

void serial_rx_byte(uint32_t data)
{
    if (data == 0x7e)
        sched_wake_tasks();
    if (receive_pos >= sizeof(receive_buf))
        return;
    receive_buf[receive_pos++] = data;
}
