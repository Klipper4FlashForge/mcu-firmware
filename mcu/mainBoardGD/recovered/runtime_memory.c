/* Small microlib runtime bodies, reconstructed from flash 080003f4..0488.
 * These are C semantic reconstructions, not copied library instructions.
 * Compile wrappers separately to retain the observed external helper calls.
 */
#include "runtime_memory.h"
#include <stdint.h>

#if defined(GD_MEMORY_COPY)
/* A word transfer may alias any object representation. The stock fast path
 * requires BOTH pointers word-aligned (0410..0422), and makes no speculative
 * reads beyond count. The unsigned address difference selects backward copy
 * exactly when destination lies in [source, source + count). */
typedef uint32_t memory_word __attribute__((__may_alias__));
void
__aeabi_memmove(void *destination, const void *source, size_t count)
{
    unsigned char *out = destination;
    const unsigned char *in = source;
    if ((uintptr_t)out - (uintptr_t)in < count) {
        out += count;
        in += count;
        while (count--) {
            *--out = *--in;
        }
    } else {
        if ((((uintptr_t)out | (uintptr_t)in) & 3) == 0) {
            while (count >= 4) {
                memory_word word = *(const memory_word *)in;
                in += 4;
                count -= 4;
                *(memory_word *)out = word;
                out += 4;
            }
        }
        while (count--) {
            *out++ = *in++;
        }
    }
}
#elif defined(GD_MEMORY_SET)
/* 0434..0442: AEABI order is r0=destination, r1=count, r2=value. */
void
__aeabi_memset(void *destination, size_t count, int value)
{
    unsigned char *out = destination;
    unsigned char byte = (unsigned char)value;
    while (count--)
        *out++ = byte;
}
#elif defined(GD_MEMORY_CLEAR)
void
__aeabi_memclr(void *destination, size_t count)
{
    __aeabi_memset(destination, count, 0);
}
#elif defined(GD_MEMORY_C_SET)
/* 0446..0458 preserves the original pointer around the AEABI helper. */
void *
memset(void *destination, int value, size_t count)
{
    __aeabi_memset(destination, count, value);
    return destination;
}
#elif defined(GD_MEMORY_COMPARE)
/* 0460/0462 byte loads are unsigned; result is the byte difference, not
 * merely -1/0/1. Both terminating bytes are fetched before either test. */
int
strcmp(const char *left, const char *right)
{
    size_t offset = 0;
    unsigned char a, b;
    for (;;) {
        a = (unsigned char)left[offset];
        b = (unsigned char)right[offset];
        if (a != b || a == 0)
            break;
        ++offset;
    }
    return (int)a - (int)b;
}
#elif defined(GD_MEMORY_SEARCH)
/* 0474 truncates the search value to unsigned byte; count zero makes no
 * memory access, and a found byte returns its address (not an index). */
void *
memchr(const void *source, int value, size_t count)
{
    const unsigned char *cursor = source;
    unsigned char byte = (unsigned char)value;
    while (count--) {
        if (*cursor == byte)
            return (void *)cursor;
        ++cursor;
    }
    return NULL;
}
#endif
