/* Scatter-loader C reconstruction. These are runtime helpers, not general
 * memcpy or an input-validating decompression API. Stock accepts linker-made
 * streams, aligned word regions and byte counts divisible by four. Its
 * decompressor processes a token even for a zero-sized output region.
 * No compressed or executable stock payload is embedded here.
 */
#include <stdint.h>

#if defined(GD_SCATTER_COPY)

void gd_runtime_copy(const uint32_t *source, uint32_t *destination,
                     uint32_t size)
{
    while (size) {
        uint32_t value = *source++;
        size -= 4;
        *destination++ = value;
    }
}

#elif defined(GD_SCATTER_NULL)

/* The retained runtime no-op at 0x08003368 is a separate BX LR entry,
 * not trailing code or alignment belonging to the copy loop. */
void gd_runtime_null(void)
{
}

#elif defined(GD_SCATTER_ZERO)

void gd_runtime_zero(const void *unused, uint32_t *destination, uint32_t size)
{
    (void)unused;
    while (size) {
        *destination++ = 0;
        size -= 4;
    }
}

#else

int32_t gd_runtime_decompress(const uint8_t *source, uint8_t *destination,
                              uint32_t size)
{
    uint8_t *end = destination + size;
    do {
        uint32_t token = *source++;
        uint32_t literals = token & 3;
        if (!literals)
            literals = *source++;
        int32_t match = token >> 4;
        if (!match)
            match = *source++;
        while (--literals)
            *destination++ = *source++;
        if (match) {
            uint32_t distance = *source++;
            uint32_t high = token & 12;
            if (high == 12)
                distance += (uint32_t)*source++ << 8;
            else
                distance += high << 6;
            const uint8_t *previous = destination - distance;
            match += 2;
            while (--match >= 0)
                *destination++ = *previous++;
        }
    } while (destination < end);
    return 0;
}

#endif
