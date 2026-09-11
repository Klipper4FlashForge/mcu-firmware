/* mainBoardGD J-Scope setup at flash 0x08000b38. Its complete 64-byte
 * function section includes the channel-name literal at 0x08000b68.
 * This advertises four int16 streams over RTT up-buffer 1. It does not
 * itself sample or transmit any motor state.
 */
#include "debug_scope.h"
#include "gd32h7xx.h"

#if defined(GD_DEBUG_SCOPE_DATA)

/* RTT publishes its identifier only after the descriptors are initialized.
 * The flash copy is reversed so a debugger cannot mistake it for the RAM
 * control block. All 16 bytes at 0x08003378..0x08003388 are included here.
 */
const char gd_rtt_reverse_id[16] = {
    0, 0, 0, 0, 0, 0, 'T', 'T', 'R', ' ', 'R', 'E', 'G', 'G', 'E', 'S'
};
const char gd_rtt_terminal_name[9] = "Terminal"; /* 0x08003738..0x08003741 */

#elif defined(GD_RTT_CONFIG)

#include "../../../klipper/lib/cmsis-core/cmsis_compiler.h"
extern void __aeabi_memclr(void *destination, size_t size);

/* Flash 0x08000550..0x0800061c, exactly 204 bytes and no literal pool.
 * Lazy initialization precedes even invalid-channel rejection. Channel 0
 * preserves its default terminal descriptor and changes only flags; channels
 * 1/2 replace their descriptor and clear read offset before write offset.
 * Architecture intrinsics provide the observed BASEPRI and DMB instructions;
 * there are no invented privilege checks or surrounding interrupt disable.
 */
int
gd_rtt_config_up_buffer(unsigned channel, const char *name,
                        void *buffer, unsigned size, unsigned flags)
{
    if (!gd_rtt_control.id[0]) {
        __aeabi_memclr(&gd_rtt_control, sizeof(gd_rtt_control));
        gd_rtt_control.max_up_buffers = 3;
        gd_rtt_control.max_down_buffers = 3;
        gd_rtt_control.up[0].name = gd_rtt_terminal_name;
        gd_rtt_control.up[0].buffer = gd_rtt_up_buffer;
        gd_rtt_control.up[0].size = 1024;
        gd_rtt_control.up[0].read_offset = 0;
        gd_rtt_control.up[0].write_offset = 0;
        gd_rtt_control.up[0].flags = 0;
        gd_rtt_control.down[0].name = gd_rtt_terminal_name;
        gd_rtt_control.down[0].buffer = gd_rtt_down_buffer;
        gd_rtt_control.down[0].size = 16;
        gd_rtt_control.down[0].read_offset = 0;
        gd_rtt_control.down[0].write_offset = 0;
        gd_rtt_control.down[0].flags = 0;
        __DMB();
        char *destination = gd_rtt_control.id;
        for (int index = 15; index >= 0; index--)
            *destination++ = gd_rtt_reverse_id[index];
        __DMB();
    }
    if (channel > 2)
        return -1;
    uint32_t previous_basepri = __get_BASEPRI();
    __set_BASEPRI(32);
    if (channel) {
        gd_rtt_control.up[channel].name = name;
        gd_rtt_control.up[channel].buffer = buffer;
        gd_rtt_control.up[channel].size = size;
        gd_rtt_control.up[channel].read_offset = 0;
        gd_rtt_control.up[channel].write_offset = 0;
    }
    gd_rtt_control.up[channel].flags = flags;
    __set_BASEPRI(previous_basepri);
    return 0;
}

#else


void
gd_jscope_init(void)
{
    (void)gd_rtt_config_up_buffer(1, "JScope_i2i2i2i2", gd_jscope_buffer, 1024, 0);
    rcu_periph_clock_enable(0x0f01);
}

#endif
