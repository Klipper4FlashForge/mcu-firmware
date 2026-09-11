/* Klipper base-command reconstruction for mainBoardGD.
 * Derived from Klipper basecmd.c, Copyright Kevin O'Connor, GPLv3.
 * Retained declarations are separate: their order/drift must not be repaired.
 */
#include <stdint.h>
#include "generated/generated.h"

extern void command_sendf(const struct command_encoder *, ...);
extern uint32_t timer_read_time(void);
extern uint8_t sched_is_shutdown(void);
extern void sched_clear_shutdown(void);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);
extern void *dynmem_start(void);
extern void *alloc_end;
extern uint16_t move_count;
extern uint32_t config_crc, stats_send_time, stats_send_time_high;

void alloc_init(void)
{
    alloc_end = (void *)(((uintptr_t)dynmem_start() + 3) & ~3u);
}

void command_get_clock(uint32_t *args)
{
    (void)args;
    const struct command_encoder *encoder = ctr_lookup_encoder("clock clock=%u");
    command_sendf(encoder, timer_read_time());
}

void command_get_uptime(uint32_t *args)
{
    (void)args;
    uint32_t now = timer_read_time();
    uint32_t high = stats_send_time_high + (now < stats_send_time);
    command_sendf(ctr_lookup_encoder("uptime high=%u clock=%u"), high, now);
}

void command_get_config(uint32_t *args)
{
    (void)args;
    const struct command_encoder *encoder = ctr_lookup_encoder(
        "config is_config=%c crc=%u is_shutdown=%c move_count=%hu");
    command_sendf(encoder, !!move_count, config_crc, sched_is_shutdown(), move_count);
}

void command_identify(uint32_t *args)
{
    uint32_t offset = args[0];
    uint8_t count = args[1];
    uint32_t size = command_identify_size;
    if (offset >= size)
        count = 0;
    else if (offset + count > size)
        count = size - offset;
    command_sendf(ctr_lookup_encoder("identify_response offset=%u data=%.*s"),
                  offset, count, &command_identify_data[offset]);
}

void command_clear_shutdown(uint32_t *args)
{
    (void)args;
    sched_clear_shutdown();
}

void command_emergency_stop(uint32_t *args)
{
    (void)args;
    sched_shutdown(ctr_lookup_static_string("Command request"));
}
