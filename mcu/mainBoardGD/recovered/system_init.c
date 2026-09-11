/* GD32H7 startup, recovered from flash 0x08000620..0x08000844.
 * Register offsets and masks are observed values; vendor field names are
 * pending SDK identification. Preserve each volatile access, including the
 * read/write with no bit change at 0x080007aa. No stock machine code is embedded.
 */
#include <stdint.h>

#define REG32(address) (*(volatile uint32_t *)(uintptr_t)(address))
#define RCU(offset) REG32(0x58024400u + (offset))
#define POWER_CONFIG REG32(0x58000468u)
#define CPACR REG32(0xe000ed88u)

void nvic_vector_table_set(uint32_t base, uint32_t offset);

void
SystemInit(void)
{
    CPACR |= 0x00f00000;
    RCU(0x00) |= 0x40000000;
    while (!(RCU(0x00) & 0x80000000))
        ;

    RCU(0x4c) |= 1;
    POWER_CONFIG &= ~1u;
    RCU(0x08) &= ~3u;
    RCU(0x00) &= 0xeaf2ffff;
    RCU(0xc4) &= 0xaffffffe;
    RCU(0x08) &= 0x00c0030c;
    RCU(0x8c) &= 0x7e003fcc;
    RCU(0x90) &= 0x88888080;
    RCU(0x94) &= 0xc3ffefc0;
    RCU(0xd0) &= ~0x301u;
    RCU(0xf0) &= 0xff888888;
    RCU(0x0c) = 0x14ff0000;
    RCU(0xcc) = 0x00700000;
    RCU(0x04) = 0x01002020;
    RCU(0x84) = 0x01012020;
    RCU(0x88) = 0x01012020;
    RCU(0x98) = 0;
    RCU(0x80) = 0x00010101;
    RCU(0xd8) = 0;
    RCU(0x9c) = 0;
    RCU(0xa0) = 0;
    RCU(0xa4) = 0;

    RCU(0x00) |= 0x00010000;
    uint32_t timeout = 0;
    uint32_t ready;
    do {
        ready = RCU(0x00) & 0x00020000;
        timeout++;
    } while (!ready && timeout != 0xffff);
    /* Stock rechecks hardware after the bounded polling loop. */
    if (!(RCU(0x00) & 0x00020000))
        for (;;)
            ;

    RCU(0x4c) |= 1;
    POWER_CONFIG |= 1;
    RCU(0x08) |= 0x80;
    RCU(0x08) |= 0x04000000;
    RCU(0x08) |= 0x20000000;
    RCU(0x08) = RCU(0x08);
    RCU(0x08) |= 0x1000;
    RCU(0x98) &= 0xfffcfff8;
    RCU(0x98) |= 0x00020002;
    RCU(0x04) &= 0x00808000;
    RCU(0x04) |= 0x01001dc5;
    RCU(0x80) &= ~0x7fu;
    RCU(0x80) |= 1;
    RCU(0x80) |= 0x03800000;
    RCU(0x00) |= 0x01000000;
    while (!(RCU(0x00) & 0x02000000))
        ;
    RCU(0x08) &= ~3u;
    RCU(0x08) |= 3;
    /* 0x0800082c..0x08000836 polls this two-bit field until value 3.
     * Its masked values are only 0, 4, 8 and 12, so <=8 retains stock's
     * single-read loop and exit condition. The candidate keeps AND/CMP but
     * still differs in the comparison endpoint and branch condition.
     */
    while ((RCU(0x08) & 0x0c) <= 8)
        ;
    nvic_vector_table_set(0x08000000, 0);
}
