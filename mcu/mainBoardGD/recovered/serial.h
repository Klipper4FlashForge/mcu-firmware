#ifndef MAINBOARDGD_RECOVERED_SERIAL_H
#define MAINBOARDGD_RECOVERED_SERIAL_H
#include <stddef.h>
#include <stdint.h>
#include "gd32h7xx.h"

/* USART0 layout confirmed by the accesses at ITCM 0x220 and 0x4550. */
struct gd_usart {
    volatile uint32_t ctl0, ctl1, ctl2, baud, guard, timeout, command;
    volatile uint32_t status, interrupt_clear, receive_data, transmit_data;
    uint32_t reserved_2c[41];
    volatile uint32_t ctl3;
};
_Static_assert(offsetof(struct gd_usart, status) == 0x1c, "USART status offset");
_Static_assert(offsetof(struct gd_usart, receive_data) == 0x24, "USART RX offset");
_Static_assert(offsetof(struct gd_usart, transmit_data) == 0x28, "USART TX offset");
_Static_assert(offsetof(struct gd_usart, ctl3) == 0xd0, "USART FIFO control offset");

/* Shared storage is supplied by the firmware layout; no duplicate buffers. */
extern uint8_t receive_buf[384], transmit_buf[96];
extern uint16_t receive_pos;
extern uint8_t transmit_pos, transmit_max;
void sched_wake_tasks(void);
void serial_init(void);
void serial_enable_tx_irq(void);
int serial_get_tx_byte(uint8_t *data);
void serial_rx_byte(uint32_t data);
void USART0_IRQHandler(void);

/* Flash-resident vendor operations reached through ITCM veneers. Each compound
 * assignment preserves a distinct volatile read/modify/write in the image. */
void gd_usart_fifo_enable(struct gd_usart *);
#endif
