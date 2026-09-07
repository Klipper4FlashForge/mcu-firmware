// Code to setup clocks and gpio on stm32f1
//
// Copyright (C) 2019-2022  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h" // CONFIG_CLOCK_REF_FREQ
#include "board/armcm_boot.h" // VectorTable
#include "board/irq.h" // irq_disable
#include "board/misc.h" // bootloader_request
#include "internal.h" // enable_pclock
#include "n32g45x.h" // NVIC_PriorityGroupConfig
#include "sched.h" // sched_main


/****************************************************************
 * Clock setup
 ****************************************************************/

#define FREQ_PERIPH (CONFIG_CLOCK_FREQ / 2)

// Map a peripheral address to its enable bits
struct cline
lookup_clock_line(uint32_t periph_base)
{
    if (periph_base >= AHBPERIPH_BASE) {
        uint32_t bit = 1 << ((periph_base - AHBPERIPH_BASE) / 0x400);
        return (struct cline){.en=&RCC->AHBENR, .bit=bit};
    } else if (periph_base >= APB2PERIPH_BASE) {
        uint32_t bit = 1 << ((periph_base - APB2PERIPH_BASE) / 0x400);
        return (struct cline){.en=&RCC->APB2ENR, .rst=&RCC->APB2RSTR, .bit=bit};
    } else {
        uint32_t bit = 1 << ((periph_base - APB1PERIPH_BASE) / 0x400);
        return (struct cline){.en=&RCC->APB1ENR, .rst=&RCC->APB1RSTR, .bit=bit};
    }
}

// Return the frequency of the given peripheral clock
uint32_t
get_pclock_frequency(uint32_t periph_base)
{
    return FREQ_PERIPH;
}

// Enable a GPIO peripheral clock
void
gpio_clock_enable(GPIO_Module *regs)
{
    uint32_t rcc_pos = ((uint32_t)regs - APB2PERIPH_BASE) / 0x400;
    volatile uint32_t *ahbpclken = &RCC->AHBENR;
    *ahbpclken |= 1 << rcc_pos;
    *ahbpclken;
}

/****************************************************************
 * GPIO setup
 ****************************************************************/

// Set the mode and extended function of a pin
void
gpio_peripheral(uint32_t gpio, uint32_t mode, int pullup)
{
    GPIO_Module *r = digital_regs[GPIO2PORT(gpio)];
    volatile uint32_t *rcc = &RCC->AHBENR;
    uint32_t bit = ((uint32_t)r - APB2PERIPH_BASE) >> 10;
    *rcc |= 1 << bit;
    *rcc;

    uint32_t pos = gpio & 15, shift = (pos & 7) * 4;
    // Pins 0-7 and 8-15 have their own alternate-function register, so
    // the two paths are spelled out separately.  Note the long-standing
    // quirk of this port: what gets shifted into the AF field is the GPIO
    // register value, not the function number.
    // Alternate functions are used on the high half of a port about as
    // often as on the low half here.
    if (__builtin_expect_with_probability(!!(pos & 8), 1, 0.6)) {
        uint32_t af = r->AFH & ~(0xf << shift);
        af |= (uint32_t)r << shift;
        r->AFH = af;
    } else {
        uint32_t af = r->AFL & ~(0xf << shift);
        af |= (uint32_t)r << shift;
        r->AFL = af;
    }

    shift = pos * 2;
    r->PMODE = ((mode & 3) << shift) | (r->PMODE & ~(3 << shift));
    uint32_t mask = ~(3 << shift);
    // Bit 4 of the mode selects open drain; the low bits are the mode
    // proper.  Only the two output modes have an output type at all.
    uint32_t kind = mode & ~GPIO_MODE_OD;
    if (kind == GPIO_MODE_OUT_PP || kind == GPIO_MODE_AF_PP)
        r->POTYPE = (((mode & GPIO_MODE_OD) >> 4) << pos)
            | (r->POTYPE & ~(1 << pos));
    r->PUPD = (pullup << shift) | (r->PUPD & mask);
    r->SR &= ~(1 << pos);
    r->DS = (GPIO_DC_8MA << shift) | (r->DS & mask);
    if (__builtin_expect_with_probability(pullup > 0, 1, 0.8)) {
        r->PBSC = 1 << pos;
    } else if (pullup) {
        r->PBSC = 1 << (pos + 16);
    }
}


/****************************************************************
 * Bootloader
 ****************************************************************/

// Reboot into USB "HID" bootloader
static void
usb_hid_bootloader(void)
{
    irq_disable();
    RCC->APB1ENR |= RCC_APB1ENR_PWREN | RCC_APB1ENR_BKPEN;
    PWR->CR |= PWR_CR_DBP;
    BKP->DR4 = 0x424C; // HID Bootloader magic key
    PWR->CR &=~ PWR_CR_DBP;
    NVIC_SystemReset();
}

// Reboot into USB "stm32duino" bootloader
static void
usb_stm32duino_bootloader(void)
{
    irq_disable();
    RCC->APB1ENR |= RCC_APB1ENR_PWREN | RCC_APB1ENR_BKPEN;
    PWR->CR |= PWR_CR_DBP;
    BKP->DR10 = 0x01; // stm32duino bootloader magic key
    PWR->CR &=~ PWR_CR_DBP;
    NVIC_SystemReset();
}

// Handle reboot requests.  These boards sit behind FlashForge's own IAP
// bootloader and never ask CanBoot for anything, so nothing is left here
// once the configured boot address is the application base.
void
bootloader_request(void)
{
    if (CONFIG_STM32_FLASH_START_800)
        usb_hid_bootloader();
    else if (CONFIG_STM32_FLASH_START_2000)
        usb_stm32duino_bootloader();
}


/****************************************************************
 * Startup
 ****************************************************************/

// Main entry point - called from armcm_boot.c:ResetHandler()
void
armcm_main(void)
{
    // Take interrupts under our own control, then point the core at our
    // vector table -- SystemInit() left VTOR at the bootloader's copy.
    __set_PRIMASK(0);
    __enable_irq();
    __DMB();
    SCB->VTOR = (uint32_t)VectorTable;
    __DSB();
    __ISB();
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_0);

    sched_main();
}
