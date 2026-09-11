#ifndef GD_DEBUG_SCOPE_H
#define GD_DEBUG_SCOPE_H

#include <stddef.h>
#include <stdint.h>

/* RTT up/down descriptors share the 24-byte target layout. The debugger
 * and target exchange read/write positions asynchronously. Control block
 * size is independently proved by the 168-byte clear at flash0x080005a8.
 */
struct gd_rtt_buffer {
    const char *name;
    void *buffer;
    uint32_t size;
    volatile uint32_t write_offset;
    volatile uint32_t read_offset;
    uint32_t flags;
};
struct gd_rtt_control_block {
    char id[16];
    uint32_t max_up_buffers;
    uint32_t max_down_buffers;
    struct gd_rtt_buffer up[3];
    struct gd_rtt_buffer down[3];
};
_Static_assert(sizeof(struct gd_rtt_buffer) == 24, "RTT descriptor size");
_Static_assert(offsetof(struct gd_rtt_buffer, write_offset) == 12, "RTT write offset");
_Static_assert(offsetof(struct gd_rtt_buffer, read_offset) == 16, "RTT read offset");
_Static_assert(offsetof(struct gd_rtt_buffer, flags) == 20, "RTT mode offset");
_Static_assert(sizeof(struct gd_rtt_control_block) == 168, "RTT block size");
_Static_assert(offsetof(struct gd_rtt_control_block, up) == 24, "RTT up descriptors");
_Static_assert(offsetof(struct gd_rtt_control_block, down) == 96, "RTT down descriptors");

extern uint8_t gd_jscope_buffer[1024];           /* 0x24002e8c */
extern struct gd_rtt_control_block gd_rtt_control; /* 0x24003298 */
extern uint8_t gd_rtt_down_buffer[16];           /* 0x24003340 */
extern uint8_t gd_rtt_up_buffer[1024];           /* 0x24003350 */
extern const char gd_rtt_reverse_id[16];        /* 0x08003378 */
extern const char gd_rtt_terminal_name[9];      /* 0x08003738 */

void gd_jscope_init(void);
int gd_rtt_config_up_buffer(unsigned channel, const char *name,
                            void *buffer, unsigned size, unsigned flags);
#endif
