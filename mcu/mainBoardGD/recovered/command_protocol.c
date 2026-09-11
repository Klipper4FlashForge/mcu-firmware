/* mainBoardGD command transport, based on Klipper command.c and generic
 * serial_irq.c / crc16_ccitt.c (Kevin O'Connor, GPLv3).
 * The three build groups preserve the original translation-unit boundaries.
 * Stock inlines parsef/msgid/VLQ helpers into dispatch and the framing encoder.
 */
#include <string.h>
#include "command_protocol.h"

/* Klipper generic/io.h semantics: these empty compiler barriers carry no ARM
 * instructions; they order the volatile byte access against surrounding work. */
#ifndef GD_PROTOCOL_CRC
static inline uint8_t readb(const void *addr)
{
    uint8_t value = *(const volatile uint8_t *)addr;
    __asm__ __volatile__("" ::: "memory");
    return value;
}
static inline void writeb(void *addr, uint8_t value)
{
    __asm__ __volatile__("" ::: "memory");
    *(volatile uint8_t *)addr = value;
}
#endif

#if defined(GD_PROTOCOL_CRC)
uint16_t crc16_ccitt(uint8_t *buf, uint32_t len)
{
    uint16_t crc = 0xffff;
    while (len--) {
        uint8_t data = *buf++;
        data ^= crc & 0xff;
        data ^= data << 4;
        crc = (((uint16_t)data << 8) | (crc >> 8))
            ^ (uint8_t)(data >> 4) ^ ((uint16_t)data << 3);
    }
    return crc;
}

#elif defined(GD_PROTOCOL_CONSOLE)
#include "serial.h"
extern uint32_t irq_save(void);
extern void irq_restore(uint32_t flags);

void console_sendf(const struct command_encoder *ce, va_list args)
{
    uint32_t tpos = readb(&transmit_pos), tmax = readb(&transmit_max);
    if (tpos >= tmax) {
        tpos = tmax = 0;
        writeb(&transmit_max, 0);
        writeb(&transmit_pos, 0);
    }
    uint32_t max_size = ce->max_size;
    if (tmax + max_size > sizeof(transmit_buf)) {
        if (tmax + max_size - tpos > sizeof(transmit_buf))
            return;
        writeb(&transmit_max, 0);
        tpos = readb(&transmit_pos);
        tmax -= tpos;
        memmove(transmit_buf, &transmit_buf[tpos], tmax);
        writeb(&transmit_pos, 0);
        writeb(&transmit_max, tmax);
        serial_enable_tx_irq();
    }
    uint32_t msglen = command_encode_and_frame(&transmit_buf[tmax], ce, args);
    writeb(&transmit_max, tmax + msglen);
    serial_enable_tx_irq();
}

static void console_pop_input(uint32_t len)
{
    uint32_t copied = 0;
    for (;;) {
        /* Stock reads only the low byte of the 16-bit receive_pos, at 0x20f2
         * and 0x2118. Preserve this shipped receive-window mismatch. */
        uint32_t rpos = readb(&receive_pos);
        uint32_t needcopy = rpos - len;
        if (needcopy) {
            memmove(&receive_buf[copied], &receive_buf[copied + len],
                    needcopy - copied);
            copied = needcopy;
            sched_wake_tasks();
        }
        uint32_t flag = irq_save();
        if (rpos != readb(&receive_pos)) {
            irq_restore(flag);
            continue;
        }
        receive_pos = needcopy;
        irq_restore(flag);
        break;
    }
}

void console_task(void)
{
    uint32_t pop_count;
    int32_t ret = command_find_block(receive_buf, readb(&receive_pos), &pop_count);
    if (ret > 0)
        command_dispatch(receive_buf, pop_count);
    if (ret) {
        console_pop_input(pop_count);
        if (ret > 0)
            command_send_ack();
    }
}

#else
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint32_t reason);
extern uint8_t sched_is_shutdown(void);
extern void sched_report_shutdown(void);
extern void irq_poll(void);
extern const char generated_string_00006dc2[];

static uint8_t *encode_int(uint8_t *p, uint32_t v)
{
    int32_t sv = v;
    if (sv < (3L << 5) && sv >= -(1L << 5)) goto f4;
    if (sv < (3L << 12) && sv >= -(1L << 12)) goto f3;
    if (sv < (3L << 19) && sv >= -(1L << 19)) goto f2;
    if (sv < (3L << 26) && sv >= -(1L << 26)) goto f1;
    *p++ = (v >> 28) | 0x80;
f1: *p++ = ((v >> 21) & 0x7f) | 0x80;
f2: *p++ = ((v >> 14) & 0x7f) | 0x80;
f3: *p++ = ((v >> 7) & 0x7f) | 0x80;
f4: *p++ = v & 0x7f;
    return p;
}

static uint32_t parse_int(uint8_t **pp)
{
    /* There is no end-pointer test inside the stock VLQ continuation loop.
     * The caller's per-argument check is deliberately not strengthened here. */
    uint8_t *p = *pp, c = *p++;
    uint32_t value = c & 0x7f;
    if ((c & 0x60) == 0x60)
        value |= -0x20;
    while (c & 0x80) {
        c = *p++;
        value = (value << 7) | (c & 0x7f);
    }
    *pp = p;
    return value;
}

static uint32_t command_parse_msgid(uint8_t **pp)
{
    uint8_t *p = *pp;
    uint32_t id = *p++;
    if (id & 0x80)
        id = ((id & 0x7f) << 7) | *p++;
    *pp = p;
    return id;
}

static uint8_t *command_parsef(uint8_t *p, uint8_t *maxend,
                            const struct command_parser *cp, uint32_t *args)
{
    uint32_t num_params = cp->num_params;
    const uint8_t *param_types = cp->param_types;
    while (num_params--) {
        if (p > maxend)
            goto error;
        uint32_t type = *param_types++;
        switch (type) {
        case PT_uint32: case PT_int32: case PT_uint16: case PT_int16: case PT_byte:
            *args++ = parse_int(&p);
            break;
        case PT_buffer: {
            uint32_t len = *p++;
            if (p + len > maxend)
                goto error;
            *args++ = len;
            *args++ = (uintptr_t)p;
            p += len;
            break;
        }
        default: goto error;
        }
    }
    return p;
error:
    sched_shutdown(ctr_lookup_static_string(generated_string_00006dc2));
}

static uint32_t command_encodef(uint8_t *buf,
                                   const struct command_encoder *ce, va_list args)
{
    uint32_t max_size = ce->max_size;
    if (max_size <= MESSAGE_MIN)
        return max_size;
    uint8_t *p = &buf[MESSAGE_HEADER_SIZE];
    uint8_t *maxend = &p[max_size - MESSAGE_MIN];
    uint32_t num_params = ce->num_params;
    const uint8_t *param_types = ce->param_types;
    uint32_t id = ce->encoded_msgid;
    if (id >= 0x80)
        *p++ = (id >> 7) | 0x80;
    *p++ = id & 0x7f;
    while (num_params--) {
        if (p > maxend)
            goto error;
        uint32_t type = *param_types++;
        uint32_t value;
        switch (type) {
        case PT_uint32: case PT_int32: case PT_uint16: case PT_int16: case PT_byte:
            value = va_arg(args, uint32_t);
            p = encode_int(p, value);
            break;
        case PT_string: {
            uint8_t *s = va_arg(args, uint8_t *), *lenp = p++;
            while (*s && p < maxend)
                *p++ = *s++;
            *lenp = p - lenp - 1;
            break;
        }
        case PT_progmem_buffer: case PT_buffer: {
            value = va_arg(args, int);
            if (value > (uint32_t)(maxend - p))
                value = maxend - p;
            *p++ = value;
            uint8_t *s = va_arg(args, uint8_t *);
            memcpy(p, s, value);
            p += value;
            break;
        }
        default: goto error;
        }
    }
    return p - buf + MESSAGE_TRAILER_SIZE;
error:
    sched_shutdown(ctr_lookup_static_string("Message encode error"));
}

uint32_t command_encode_and_frame(uint8_t *buf,
                                     const struct command_encoder *ce, va_list args)
{
    uint32_t len = command_encodef(buf, ce, args);
    buf[0] = len;
    buf[1] = next_sequence;
    uint16_t crc = crc16_ccitt(buf, len - MESSAGE_TRAILER_SIZE);
    buf[len - 3] = crc >> 8;
    buf[len - 2] = crc;
    buf[len - 1] = MESSAGE_SYNC;
    return len;
}

void command_sendf(const struct command_encoder *ce, ...)
{
    if (readb(&in_sendf))
        return;
    writeb(&in_sendf, 1);
    va_list args;
    va_start(args, ce);
    console_sendf(ce, args);
    va_end(args);
    writeb(&in_sendf, 0);
}

void sendf_shutdown(void) { writeb(&in_sendf, 0); }

int32_t command_find_block(uint8_t *buf, uint32_t buf_len,
                              uint32_t *pop_count)
{
    enum { CF_NEED_SYNC = 1, CF_NEED_VALID = 2 };
    if (buf_len && (command_sync_state & CF_NEED_SYNC))
        goto need_sync;
    if (buf_len < MESSAGE_MIN)
        goto need_more_data;
    uint32_t len = buf[0];
    if (len < MESSAGE_MIN || len > MESSAGE_MAX)
        goto error;
    uint32_t seq = buf[1];
    if ((seq & ~MESSAGE_SEQ_MASK) != MESSAGE_DEST)
        goto error;
    if (buf_len < len)
        goto need_more_data;
    if (buf[len - 1] != MESSAGE_SYNC)
        goto error;
    uint16_t msgcrc = (buf[len - 3] << 8) | buf[len - 2];
    if (crc16_ccitt(buf, len - 3) != msgcrc)
        goto error;
    command_sync_state &= ~CF_NEED_VALID;
    *pop_count = len;
    if (seq != next_sequence)
        goto nak;
    next_sequence = ((seq + 1) & MESSAGE_SEQ_MASK) | MESSAGE_DEST;
    return 1;
need_more_data:
    *pop_count = 0;
    return 0;
error:
    if (buf[0] == MESSAGE_SYNC) {
        *pop_count = 1;
        return -1;
    }
    command_sync_state |= CF_NEED_SYNC;
need_sync:;
    uint8_t *next_sync = memchr(buf, MESSAGE_SYNC, buf_len);
    if (next_sync) {
        command_sync_state &= ~CF_NEED_SYNC;
        *pop_count = next_sync - buf + 1;
    } else {
        *pop_count = buf_len;
    }
    if (command_sync_state & CF_NEED_VALID)
        return -1;
    command_sync_state |= CF_NEED_VALID;
nak:
    command_sendf(&encode_acknak);
    return -1;
}

void command_dispatch(uint8_t *buf, uint32_t len)
{
    uint8_t *p = &buf[2], *end = &buf[len - 3];
    while (p < end) {
        uint32_t id = command_parse_msgid(&p);
        if (!id || id >= command_index_size)
            sched_shutdown(ctr_lookup_static_string("Invalid command"));
        const struct command_parser *cp = &command_index[id];
        uint32_t args[cp->num_args];
        p = command_parsef(p, end, cp, args);
        if (sched_is_shutdown() && !(cp->flags & 1)) {
            sched_report_shutdown();
            continue;
        }
        irq_poll();
        cp->func(args);
    }
}

void command_send_ack(void) { command_sendf(&encode_acknak); }
#endif
