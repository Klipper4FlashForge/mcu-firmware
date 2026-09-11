/* USART and clock vendor operations recovered from flash 0x08002158..0x08003198.
 * Configuration arguments are already positioned register fields, as in the
 * observed serial_init callers. USART enable is cleared before format/FIFO
 * changes; separate volatile assignments retain all observed accesses.
 */
#include "serial.h"

/* The rest of this file was GigaDevice's usart/rcu code, now compiled from
 * lib/gd32h7xx. This 22-byte FIFO enable has no counterpart in that V1.1.0
 * library (its usart_fifo_enable is 14 bytes) and stays reconstructed. */
void gd_usart_fifo_enable(struct gd_usart *usart)
{
    usart->ctl0 &= ~1U;
    usart->ctl3 |= 0x100U;
}
