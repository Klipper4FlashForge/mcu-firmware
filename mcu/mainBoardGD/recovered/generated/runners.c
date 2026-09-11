/* Recovered from actual branch order, not retained .ctr order.
 * watchdog_init/watchdog_reset declarations have no corresponding
 * call in the shipped generated runners.
 * mclib_init here names the Klipper wrapper at 0x3d00. */
#include "generated.h"

extern void alloc_init(void);
extern void analog_in_shutdown(void);
extern void analog_in_task(void);
extern void buttons_task(void);
extern void clear_active_irq(void);
extern void console_task(void);
extern void digital_out_shutdown(void);
extern void initial_pins_setup(void);
extern void irq_poll(void);
extern void mclib_init(void);
extern void move_reset(void);
extern void sendf_shutdown(void);
extern void serial_init(void);
extern void stepper_shutdown(void);
extern void timer_cnt_init(void);
extern void timer_reset(void);
extern void timer_task(void);
extern void trsync_shutdown(void);
extern void trsync_task(void);

/* Stock 0x000027c8: 26 code bytes; following alignment is separate. */
void
ctr_run_initfuncs(void)
{
    alloc_init(); // 0x000007a8
    initial_pins_setup(); // 0x00003878
    timer_cnt_init(); // 0x00004ec8
    mclib_init(); // 0x00003d00
    serial_init(); // 0x000045a0
}

/* Stock 0x000027e8: 38 code bytes; following alignment is separate. */
void
ctr_run_shutdownfuncs(void)
{
    sendf_shutdown(); // 0x00004518
    move_reset(); // 0x00003ed8
    digital_out_shutdown(); // 0x00002988
    stepper_shutdown(); // 0x000048b0
    trsync_shutdown(); // 0x000059d0
    analog_in_shutdown(); // 0x00000868
    clear_active_irq(); // 0x00000b10
    timer_reset(); // 0x00005590
}

/* Stock 0x00002810: 50 code bytes; following alignment is separate. */
void
ctr_run_taskfuncs(void)
{
    irq_poll(); // 0x00003890
    trsync_task(); // 0x00005a40
    irq_poll(); // 0x00003890
    analog_in_task(); // 0x000008d0
    irq_poll(); // 0x00003890
    buttons_task(); // 0x00000a58
    irq_poll(); // 0x00003890
    timer_task(); // 0x00005868
    irq_poll(); // 0x00003890
    console_task(); // 0x000020d8
    irq_poll(); // 0x00003890
}

