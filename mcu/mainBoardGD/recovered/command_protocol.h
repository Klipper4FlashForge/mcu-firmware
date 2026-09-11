#ifndef MAINBOARDGD_RECOVERED_COMMAND_PROTOCOL_H
#define MAINBOARDGD_RECOVERED_COMMAND_PROTOCOL_H
#include <stdarg.h>
#include "generated/generated.h"

/* Protocol counts use word-sized fast integers in stock: pop_count is written
 * with STR, not STRB. ATfE's current stdint fast8 typedef is byte-sized, so spell
 * these recovered API and local types explicitly as 32-bit integers. */

enum {
    MESSAGE_MIN = 5, MESSAGE_MAX = 64, MESSAGE_HEADER_SIZE = 2,
    MESSAGE_TRAILER_SIZE = 3, MESSAGE_SYNC = 0x7e,
    MESSAGE_SEQ_MASK = 0x0f, MESSAGE_DEST = 0x10,
};
extern uint8_t next_sequence, command_sync_state, in_sendf;
extern const struct command_encoder encode_acknak;
uint16_t crc16_ccitt(uint8_t *buf, uint32_t len);
uint32_t command_encode_and_frame(uint8_t *buf,
    const struct command_encoder *ce, va_list args);
void command_sendf(const struct command_encoder *ce, ...);
void sendf_shutdown(void);
int32_t command_find_block(uint8_t *buf, uint32_t len,
                              uint32_t *pop_count);
void command_dispatch(uint8_t *buf, uint32_t len);
void command_send_ack(void);
void console_sendf(const struct command_encoder *ce, va_list args);
void console_task(void);
#endif
