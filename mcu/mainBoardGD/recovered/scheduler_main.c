/* Scheduler startup, task loop and shutdown reporting from stock mainBoardGD.
 * Derived from Klipper sched.c, Copyright Kevin O'Connor, GPLv3.
 * The levelBoard-specific eddy operations are absent from this image.
 */
#include <stdint.h>
#include "state.h"
#include "generated/generated.h"

extern void irq_disable(void), irq_enable(void), irq_poll(void), irq_wait(void);
extern uint32_t timer_read_time(void);
extern void timer_kick(void), stats_update(uint32_t start, uint32_t end);
extern void command_sendf(const struct command_encoder *, ...);
extern void ctr_run_initfuncs(void), ctr_run_shutdownfuncs(void), ctr_run_taskfuncs(void);
extern int8_t tasks_status;
extern uint8_t shutdown_status, shutdown_reason, ff_timer_close;
extern uint32_t ff_close_num, ff_temp_waketime;
extern uint64_t shutdown_jmp[20];
extern __attribute__((returns_twice)) int setjmp(void *environment);
extern const char generated_string_00006d10[];

static void report_close(void)
{
    command_sendf(ctr_lookup_encoder(generated_string_00006d10),
                  ff_timer_close, ff_close_num, ff_temp_waketime);
}

void sched_report_shutdown(void)
{
    report_close();
    command_sendf(ctr_lookup_encoder("is_shutdown static_string_id=%hu"),
                  shutdown_reason);
}

static void run_shutdown(int reason)
{
    irq_disable();
    uint32_t now = timer_read_time();
    if (!shutdown_status)
        shutdown_reason = reason;
    shutdown_status = 2;
    sched_timer_list = &deleted_timer;
    deleted_timer.waketime = periodic_timer.waketime;
    deleted_timer.next = sched_last_insert = &periodic_timer;
    periodic_timer.next = &sentinel_timer;
    timer_kick();
    ctr_run_shutdownfuncs();
    shutdown_status = 1;
    irq_enable();
    report_close();
    command_sendf(ctr_lookup_encoder("shutdown clock=%u static_string_id=%hu"),
                  now, shutdown_reason);
}

__attribute__((noreturn)) void sched_main(void)
{
    ctr_run_initfuncs();
    command_sendf(ctr_lookup_encoder("starting"));
    irq_disable();
    int reason = setjmp(shutdown_jmp);
    if (reason)
        run_shutdown(reason);
    irq_enable();
    uint32_t task_start = timer_read_time();
    for (;;) {
        irq_poll();
        if (tasks_status != 0) {
            task_start -= timer_read_time();
            irq_disable();
            if (tasks_status != 0) {
                tasks_status = -1;
                do {
                    irq_wait();
                } while (tasks_status != 0);
            }
            irq_enable();
            task_start += timer_read_time();
        }
        tasks_status = 1;
        ctr_run_taskfuncs();
        uint32_t now = timer_read_time();
        stats_update(task_start, now);
        task_start = now;
    }
}
