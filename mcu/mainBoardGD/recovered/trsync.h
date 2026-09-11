#ifndef MAINBOARDGD_RECOVERED_TRSYNC_H
#define MAINBOARDGD_RECOVERED_TRSYNC_H

#include "stepper.h" /* shared timer and trigger-signal ABI */

struct trsync {
    struct timer report_time, expire_time;
    uint32_t report_ticks;
    struct trsync_signal *signals;
    uint8_t flags, trigger_reason, expire_reason;
};
_Static_assert(sizeof(struct trsync) == 36, "trigger-sync OID allocation");
_Static_assert(offsetof(struct trsync, signals) == 28, "trigger signal list");
_Static_assert(offsetof(struct trsync, flags) == 32, "trigger flags");
struct task_wake { volatile uint8_t wake; };
extern struct task_wake trsync_wake; /* observed BSS 0x24008b16 */

void trsync_do_trigger(struct trsync *, uint8_t reason);
uint_fast8_t trsync_expire_event(struct timer *);
uint_fast8_t trsync_report_event(struct timer *);
void command_config_trsync(uint32_t *args);
void command_trsync_start(uint32_t *args);
void command_trsync_set_timeout(uint32_t *args);
void command_trsync_trigger(uint32_t *args);
void trsync_task(void);
void trsync_shutdown(void);
#endif
