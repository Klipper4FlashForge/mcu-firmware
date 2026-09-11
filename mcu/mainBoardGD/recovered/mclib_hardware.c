/* Full hardware entry, flash 08001710..08001f88 (2168 bytes, no pools).
 * Called by the registered ITCM mclib_init wrapper; it is not that wrapper.
 * API names describe the register consumers, not a pinned SDK release.
 * Macro expansion preserves the explicit repeated call sites and call order.
 */
#include "mclib_hardware.h"
#include "gpio.h"


#define PWM_PIN(base, alternate, pin) do { \
    gpio_af_set(base, alternate, pin); \
    gpio_mode_set(base, 2, 0, pin); \
    gpio_output_options_set(base, 0, 1, pin); \
} while (0)
#define PWM_STATE(state, peripheral) do { \
    (state).timer = peripheral; \
    (state).half_period_ticks = 7500; \
    (state).channels[0] = 0; \
    (state).channels[1] = 1; \
    (state).channels[2] = 2; \
    (state).channels[3] = 3; \
    mclib_pwm_init(&(state)); \
} while (0)
#define MOTOR_TIMER_BASE(peripheral, divider, top) do { \
    timer_deinit(peripheral); \
    timer_struct_para_init(&scratch.timer); \
    scratch.timer.period = top; \
    scratch.timer.prescaler = divider; \
    scratch.timer.alignedmode = 0; \
    scratch.timer.counterdirection = 0; \
    scratch.timer.clockdivision = 0; \
    scratch.timer.repetitioncounter = 0; \
    timer_init(peripheral, &scratch.timer); \
} while (0)
#define TIMER_OUTPUTS(peripheral) do { \
    output.outputstate = 1; \
    output.outputnstate = 0; \
    output.ocpolarity = 0; \
    output.ocnpolarity = 0; \
    output.ocidlestate = 0; \
    output.ocnidlestate = 0; \
    timer_channel_output_config(peripheral, 0, &output); \
    timer_channel_output_config(peripheral, 1, &output); \
    timer_channel_output_config(peripheral, 2, &output); \
    timer_channel_output_config(peripheral, 3, &output); \
} while (0)
#define TIMER_PHASE(peripheral, channel, pulse) do { \
    timer_channel_output_mode_config(peripheral, channel, 0x70); \
    timer_channel_output_shadow_config(peripheral, channel, 8); \
    timer_channel_output_pulse_value_config(peripheral, channel, pulse); \
} while (0)
#define TIMER_SLAVE(peripheral, trigger) do { \
    timer_input_trigger_source_select(peripheral, trigger); \
    timer_slave_mode_select(peripheral, 5); \
} while (0)
#define ADC_SETUP(peripheral, regular0, regular1, inserted0, inserted1) do { \
    adc_deinit(peripheral); \
    adc_clock_config(peripheral, 0xa0000); \
    adc_special_function_config(peripheral, 0x100, 1); \
    adc_resolution_config(peripheral, 0); \
    adc_data_alignment_config(peripheral, 0); \
    adc_channel_length_config(peripheral, 1, 2); \
    adc_regular_channel_config(peripheral, 0, regular0, 0); \
    adc_regular_channel_config(peripheral, 1, regular1, 0); \
    adc_external_trigger_config(peripheral, 1, 1); \
    adc_dma_request_after_last_enable(peripheral); \
    adc_dma_mode_enable(peripheral); \
    adc_channel_length_config(peripheral, 2, 2); \
    adc_inserted_channel_config(peripheral, 0, inserted0, 0); \
    adc_inserted_channel_config(peripheral, 1, inserted1, 0); \
    adc_external_trigger_config(peripheral, 2, 1); \
    adc_interrupt_flag_clear(peripheral, 4); \
    adc_interrupt_enable(peripheral, 0x80); \
    adc_enable(peripheral); \
    /* Actual NOP stabilization loops at 1d2c and 1df8: 6001 iterations. \
     * This intrinsic retains their effect; exact cycle scheduling is ungated. */ \
    for (uint32_t delay = 6001; delay != 0; --delay) \
        __builtin_arm_nop(); \
    adc_calibration_mode_config(peripheral, 0x08000000); \
    adc_calibration_number(peripheral, 0); \
    adc_calibration_enable(peripheral); \
} while (0)
#define DMA_SETUP(channel, request_id, adc_data, buffer) do { \
    dma_deinit(0x40020000, channel); \
    scratch.dma.request = request_id; \
    scratch.dma.periph_addr = adc_data; \
    scratch.dma.periph_inc = 1; \
    scratch.dma.memory0_addr = (uint32_t)(uintptr_t)(buffer); \
    scratch.dma.memory_inc = 0; \
    scratch.dma.periph_memory_width = 0x1000; \
    /* circular_mode (+24) is intentionally not initialized: stock sp+40. */ \
    scratch.dma.direction = 0; \
    scratch.dma.number = 2; \
    scratch.dma.priority = 0x30000; \
    dma_single_data_mode_init(0x40020000, channel, &scratch.dma); \
    dma_circulation_enable(0x40020000, channel); \
    dma_channel_enable(0x40020000, channel); \
    dma_flag_clear(0x40020000, channel, 0x20); \
    dma_interrupt_enable(0x40020000, channel, 0x10); \
} while (0)

void
mclib_hardware_init(void)
{
    timer_oc_parameter_struct output;
    /* The stock frame reuses sp+16 for timer parameters then DMA parameters.
     * Do not clear this union: both untouched timer padding and DMA circular_mode
     * are real uncertainties. The latter is consumed at ITCM 0x2d34. */
    union {
        timer_parameter_struct timer;
        dma_single_data_parameter_struct dma;
    } scratch;

    /* 1732..181a: Y PWM, GPIO C6..9, analog C4/C5, timer 0x40010400. */
    rcu_periph_clock_enable(0x0f02);
    rcu_periph_clock_enable(0x1101);
    PWM_PIN(0x58020800, 3, 0x40);
    PWM_PIN(0x58020800, 3, 0x80);
    PWM_PIN(0x58020800, 3, 0x100);
    PWM_PIN(0x58020800, 3, 0x200);
    gpio_mode_set(0x58020800, 3, 0, 0x10);
    gpio_mode_set(0x58020800, 3, 0, 0x20);
    PWM_STATE(mclib_pwm_y, 0x40010400);

    /* 181e..18ec: X PWM, GPIO B6..9, analog B0/B1. */
    rcu_periph_clock_enable(0x0f01);
    rcu_periph_clock_enable(0x1002);
    PWM_PIN(0x58020400, 2, 0x40);
    PWM_PIN(0x58020400, 2, 0x80);
    PWM_PIN(0x58020400, 2, 0x100);
    PWM_PIN(0x58020400, 2, 0x200);
    gpio_mode_set(0x58020400, 3, 0, 1);
    gpio_mode_set(0x58020400, 3, 0, 2);
    PWM_STATE(mclib_pwm_x, 0x40000800);

    /* 18f0..19b0: Z PWM, GPIO A0..3, analog A6/A7. No extruder PWM
     * object setup occurs in this body: do not invent a fourth copy. */
    rcu_periph_clock_enable(0x0f00);
    rcu_periph_clock_enable(0x1000);
    PWM_PIN(0x58020000, 1, 1);
    PWM_PIN(0x58020000, 1, 2);
    PWM_PIN(0x58020000, 1, 4);
    PWM_PIN(0x58020000, 1, 8);
    gpio_mode_set(0x58020000, 3, 0, 0x40);
    gpio_mode_set(0x58020000, 3, 0, 0x80);
    PWM_STATE(mclib_pwm_z, 0x40000000);

    rcu_periph_clock_enable(0x111f);
    gd_motor_syscfg_route(0xa0, 0x2c);
    gd_motor_syscfg_route(0x10, 0x3a);
    gd_motor_syscfg_route(0x98, 0x2d);
    gd_motor_syscfg_route(0x11, 0x3b);
    gd_motor_syscfg_route(0x90, 0x2e);
    gd_motor_syscfg_route(0x14, 0x38);
    gd_motor_syscfg_route(0x8c, 0x2f);
    gd_motor_syscfg_route(0x15, 0x39);

    /* 19fc..1b50: phase-staggered conversion trigger and four slave timers. */
    rcu_periph_clock_enable(0x1300);
    rcu_periph_clock_enable(0x1001);
    MOTOR_TIMER_BASE(0x40000400, 0, 14999);
    TIMER_OUTPUTS(0x40000400);
    TIMER_PHASE(0x40000400, 0, 1000);
    TIMER_PHASE(0x40000400, 1, 4750);
    TIMER_PHASE(0x40000400, 2, 8500);
    TIMER_PHASE(0x40000400, 3, 12250);
    timer_master_slave_mode_config(0x40000400, 0x80);
    timer_master_output0_trigger_source_select(0x40000400, 0x10);
    TIMER_SLAVE(0x40010000, 0x13);
    TIMER_SLAVE(0x40000000, 0x13);
    TIMER_SLAVE(0x40000800, 0x13);
    TIMER_SLAVE(0x40010400, 0x13);

    /* 1b54..1c60: second trigger is 120 counts after the first. */
    rcu_periph_clock_enable(0x1300);
    rcu_periph_clock_enable(0x1003);
    MOTOR_TIMER_BASE(0x40000c00, 0, 14999);
    TIMER_OUTPUTS(0x40000c00);
    TIMER_PHASE(0x40000c00, 0, 1120);
    TIMER_PHASE(0x40000c00, 1, 4870);
    TIMER_PHASE(0x40000c00, 2, 8620);
    TIMER_PHASE(0x40000c00, 3, 12370);
    TIMER_SLAVE(0x40000c00, 3);

    rcu_periph_clock_enable(0x1108);
    rcu_periph_clock_enable(0x1109);
    rcu_periph_clock_enable(0x0c15);
    rcu_periph_clock_enable(0x0c17);
    ADC_SETUP(0x40012400, 8, 4, 5, 9);
    ADC_SETUP(0x40012800, 7, 3, 18, 19);

    /* 1e18..1e60: regular samples arrive via DMA for Y/Z; inserted
     * samples for X/E are read directly from the ADC register pairs. */
    mclib_acquisition_y.adc = 0x40012400;
    mclib_acquisition_y.sample_registers = mclib_adc_dma_y;
    mclib_acquisition_x.adc = 0x40012400;
    mclib_acquisition_x.sample_registers = (volatile uint32_t *)0x40012454;
    mclib_acquisition_z.adc = 0x40012800;
    mclib_acquisition_z.sample_registers = mclib_adc_dma_z;
    mclib_acquisition_extruder.adc = 0x40012800;
    mclib_acquisition_extruder.sample_registers = (volatile uint32_t *)0x40012854;
    DMA_SETUP(0, 9, 0x40012464, mclib_adc_dma_y);
    DMA_SETUP(1, 10, 0x40012864, mclib_adc_dma_z);

    nvic_priority_group_set(0x500);
    nvic_irq_enable(11, 1, 0);
    nvic_irq_enable(12, 1, 0);
    nvic_irq_enable(18, 1, 0);
    rcu_periph_clock_enable(0x1006);
    MOTOR_TIMER_BASE(0x4000e000, 2, UINT32_MAX);
    timer_enable(0x4000e000);
}
