/* mainBoardGD console initialization and byte/FIFO interrupt path.
 * Reconstructed from ITCM 0x220, 0x4550, 0x4568, 0x45a0 and 0x4698.
 * Generic buffering follows Klipper's serial_irq.c, retaining this image's
 * 16-bit receive position and its observed transmit-position store order.
 */
#include "serial.h"
#include "gpio.h"

/* The SDK names USART0 by its base address; the register struct is local. */
#define USART0_REGS ((struct gd_usart *)USART0)
#define CONSOLE_CTL0 0x2dU
#define TX_FIFO_IRQ_MASK 0xa0000000U

extern void gd_usart_fifo_enable(struct gd_usart *);

void serial_init(void)
{
    rcu_periph_clock_enable(0xf00);
    rcu_periph_clock_enable(0x1104);
    gpio_af_set(GPIOA, 7, 1U << 10);
    gpio_mode_set(GPIOA, 2, 1, 1U << 10);
    gpio_output_options_set(GPIOA, 0, 3, 1U << 10);
    gpio_af_set(GPIOA, 7, 1U << 9);
    gpio_mode_set(GPIOA, 2, 1, 1U << 9);
    gpio_output_options_set(GPIOA, 0, 3, 1U << 9);
    usart_deinit(USART0);
    usart_baudrate_set(USART0, 230400);
    usart_stop_bit_set(USART0, 0);
    usart_word_length_set(USART0, 0);
    usart_parity_config(USART0, 0);
    usart_hardware_flow_rts_config(USART0, 0);
    usart_hardware_flow_cts_config(USART0, 0);
    usart_receive_config(USART0, 4);
    usart_transmit_config(USART0, 8);
    usart_transmit_fifo_threshold_config(USART0, 0x100000);
    usart_receive_fifo_threshold_config(USART0, 0x20000);
    gd_usart_fifo_enable(USART0_REGS);
    usart_enable(USART0);
    *(volatile uint8_t *)0xe000e425 = 0; /* NVIC priority, IRQ37 */
    *(volatile uint32_t *)0xe000e104 = 1U << 5; /* NVIC ISER1 */
}

void serial_enable_tx_irq(void)
{
    USART0_REGS->ctl0 = CONSOLE_CTL0;
    USART0_REGS->ctl3 |= TX_FIFO_IRQ_MASK;
}

void USART0_IRQHandler(void)
{
    if (USART0_REGS->status & (1U << 5))
        serial_rx_byte(USART0_REGS->receive_data);
    if ((USART0_REGS->ctl3 & 0x03000000U) && (USART0_REGS->ctl3 & TX_FIFO_IRQ_MASK)) {
        do {
            uint8_t data;
            if (serial_get_tx_byte(&data)) {
                USART0_REGS->ctl0 = CONSOLE_CTL0;
                USART0_REGS->ctl3 &= ~TX_FIFO_IRQ_MASK;
                return;
            }
            USART0_REGS->transmit_data = data;
        } while (!(USART0_REGS->ctl3 & (1U << 7)));
    }
}
