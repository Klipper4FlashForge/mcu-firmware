/* Motor sample interrupt dispatch, reconstructed from ITCM at address zero.
 * IRQ18 services ADC X/E flags in order; IRQ11/12 service DMA Y/Z samples.
 * Calibration must finish before invoking the corresponding control loop.
 */
#include "mclib_state.h"
extern struct mclib_motor mclib_motor_x, mclib_motor_y, mclib_motor_z;
extern struct mclib_motor mclib_motor_extruder;
uint32_t adc_interrupt_flag_get(uint32_t adc, uint32_t flag);

uint32_t dma_interrupt_flag_get(uint32_t dma, uint32_t channel, uint32_t flag);
void dma_interrupt_flag_clear(uint32_t dma, uint32_t channel, uint32_t flag);

void gd_motor_adc_irq(void)
{
    if (adc_interrupt_flag_get(0x40012400, 4)) {
        adc_interrupt_flag_clear(0x40012400, 4);
        if (!mclib_current_acquisition_calibrate(mclib_motor_x.current_acquisition))
            mclib_control_loop_a(&mclib_motor_x);
    }
    if (adc_interrupt_flag_get(0x40012800, 4)) {
        adc_interrupt_flag_clear(0x40012800, 4);
        if (!mclib_current_acquisition_calibrate(mclib_motor_extruder.current_acquisition))
            mclib_control_loop_b(&mclib_motor_extruder);
    }
}

void gd_motor_dma0_irq(void)
{
    if (dma_interrupt_flag_get(0x40020000, 0, 32)) {
        dma_interrupt_flag_clear(0x40020000, 0, 32);
        if (!mclib_current_acquisition_calibrate(mclib_motor_y.current_acquisition))
            mclib_control_loop_a(&mclib_motor_y);
    }
}

void gd_motor_dma1_irq(void)
{
    if (dma_interrupt_flag_get(0x40020000, 1, 32)) {
        dma_interrupt_flag_clear(0x40020000, 1, 32);
        if (!mclib_current_acquisition_calibrate(mclib_motor_z.current_acquisition))
            mclib_control_loop_b(&mclib_motor_z);
    }
}

/* Deliberate stock fault traps, not unrecovered function stubs. */
void BusFault_Handler(void) { for (;;) {} }
void DebugMon_Handler(void) { for (;;) {} }
void HardFault_Handler(void) { for (;;) {} }
void MemManage_Handler(void) { for (;;) {} }
void NMI_Handler(void) { for (;;) {} }
void PendSV_Handler(void) { for (;;) {} }
void SVC_Handler(void) { for (;;) {} }
void UsageFault_Handler(void) { for (;;) {} }
