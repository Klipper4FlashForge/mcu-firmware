/* Klipper task statistics, with mainBoardGD's unsigned elapsed-time test.
 * Derived from basecmd.c, Copyright Kevin O'Connor, GPLv3.
 */
#include <stdint.h>
#include "generated/generated.h"

extern uint32_t stats_count, stats_sum, stats_sumsq;
extern uint32_t stats_send_time, stats_send_time_high;
extern uint32_t timer_from_us(uint32_t usecs);
extern void command_sendf(const struct command_encoder *, ...);

void stats_update(uint32_t start, uint32_t now)
{
    uint32_t diff = now - start;
    stats_count++;
    stats_sum += diff;
    uint32_t next_sumsq;
    if (diff <= 0xffff)
        next_sumsq = stats_sumsq + ((diff * diff + 255) / 256);
    else if (diff <= 0xfffff)
        next_sumsq = stats_sumsq + ((diff + 255) / 256) * diff;
    else
        next_sumsq = 0xffffffff;
    /* Stock 0x472a reloads the accumulator before saturation, separately
     * from the selected arithmetic branch's read at 0x4708/0x471c. */
    if (next_sumsq < *(volatile uint32_t *)&stats_sumsq)
        next_sumsq = 0xffffffff;
    stats_sumsq = next_sumsq;
    /* Preserve the timestamp snapshot across the timer conversion call;
     * stock computes the elapsed interval after that call at 0x474c. */
    uint32_t previous_send_time = stats_send_time;
    uint32_t period = timer_from_us(5000000);
    if (now - previous_send_time < period)
        return;
    command_sendf(ctr_lookup_encoder("stats count=%u sum=%u sumsq=%u"),
                  stats_count, stats_sum, stats_sumsq);
    if (stats_send_time > now)
        stats_send_time_high++;
    stats_send_time = now;
    stats_count = stats_sum = stats_sumsq = 0;
}
