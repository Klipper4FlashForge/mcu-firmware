// Code to setup clocks and gpio on stm32f1
//
// Copyright (C) 2019-2022  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h" // CONFIG_CLOCK_REF_FREQ
#include "board/armcm_boot.h" // VectorTable
#include "board/armcm_reset.h" // try_request_canboot
#include "board/irq.h" // irq_disable
#include "board/misc.h" // bootloader_request
#include "internal.h" // enable_pclock
#include "sched.h" // sched_main
#include "../../lib/n32g45x/include/n32g45x.h"

extern void NVIC_PriorityGroupConfig(uint32_t);


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
gpio_clock_enable(GPIO_TypeDef *regs)
{
    uint32_t rcc_pos = ((uint32_t)regs - APB2PERIPH_BASE) / 0x400;
    volatile uint32_t *ahbpclken = (volatile uint32_t *)0x40021014;
    *ahbpclken |= 1 << rcc_pos;
    *ahbpclken;
}

// Main clock setup called at chip startup
static void
clock_setup(void)
{
    // Configure and enable PLL
    uint32_t cfgr;
    if (!CONFIG_STM32_CLOCK_REF_INTERNAL) {
        // Configure 72Mhz PLL from external crystal (HSE)
        RCC->CR |= RCC_CR_HSEON;
        uint32_t div = CONFIG_CLOCK_FREQ / (CONFIG_CLOCK_REF_FREQ / 2);
        cfgr = 1 << RCC_CFGR_PLLSRC_Pos;
        if ((div & 1) && div <= 16)
            cfgr |= RCC_CFGR_PLLXTPRE_HSE_DIV2;
        else
            div /= 2;
        cfgr |= (div - 2) << RCC_CFGR_PLLMULL_Pos;
    } else {
        // Configure 72Mhz PLL from internal 8Mhz oscillator (HSI)
        uint32_t div2 = (CONFIG_CLOCK_FREQ / 8000000) * 2;
        cfgr = ((0 << RCC_CFGR_PLLSRC_Pos)
                | ((div2 - 2) << RCC_CFGR_PLLMULL_Pos));
    }
    cfgr |= RCC_CFGR_PPRE1_DIV2 | RCC_CFGR_PPRE2_DIV2 | RCC_CFGR_ADCPRE_DIV8;
    RCC->CFGR = cfgr;
    RCC->CR |= RCC_CR_PLLON;

    // Set flash latency
    FLASH->ACR = (2 << FLASH_ACR_LATENCY_Pos) | FLASH_ACR_PRFTBE;

    // Wait for PLL lock
    while (!(RCC->CR & RCC_CR_PLLRDY))
        ;

    // Switch system clock to PLL
    RCC->CFGR = cfgr | RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS_Msk) != RCC_CFGR_SWS_PLL)
        ;
}


/****************************************************************
 * GPIO setup
 ****************************************************************/

static void
stm32f1_alternative_remap(uint32_t mapr_mask, uint32_t mapr_value)
{
    // The MAPR register is a mix of write only and r/w bits
    // We have to save the written values in a global variable
    static uint32_t mapr = 0;

    mapr &= ~mapr_mask;
    mapr |= mapr_value;
    AFIO->MAPR = mapr;
}

#define STM_OSPEED 0x1 // ~10Mhz at 50pF

// Set the mode and extended function of a pin
void
gpio_peripheral(uint32_t gpio, uint32_t mode, int pullup)
{
    GPIO_Module *r = (GPIO_Module *)digital_regs[GPIO2PORT(gpio)];
    volatile uint32_t *rcc = (volatile uint32_t *)0x40021014;
    uint32_t bit = ((uint32_t)r + 0xbfff0000) >> 10;
    *rcc |= 1 << bit;
    *rcc;

    uint32_t pos = gpio & 15, shift = (pos & 7) * 4;
    // The stock port spells the two AF register paths separately.  It also
    // shifts the GPIO register value itself into the AF field; retain that
    // original quirk for binary and behavioral fidelity.
    // The branch probabilities decide where GCC parks the two out-of-line
    // blocks (the AFL write and the POTYPE write) relative to each other and
    // to the pullup tail; these weights reproduce stock's block order.
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
    if ((mode & 0xffffffef) - 1 < 2)
        r->POTYPE = (((mode & 0x1f) >> 4) << pos)
            | (r->POTYPE & ~(1 << pos));
    r->PUPD = (pullup << shift) | (r->PUPD & mask);
    r->SR &= ~(1 << pos);
    r->DS = (2 << shift) | (r->DS & mask);
    if (__builtin_expect_with_probability(pullup < 1, 1, 0.2)) {
        if (pullup)
            r->PBSC = 1 << (pos + 16);
    } else {
        r->PBSC = 1 << pos;
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

// Handle reboot requests.  Stock's copy is an empty function: it never
// asks CanBoot for anything (the image sits behind FlashForge's own IAP
// bootloader), so try_request_canboot() is not linked at all.
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
    // Restore VTOR after reset-stage clock setup.
    asm volatile("movs r3, #0\n msr primask, r3");
    __enable_irq();
    __DMB();
    SCB->VTOR = (uint32_t)VectorTable;
    __DSB();
    __ISB();
    NVIC_PriorityGroupConfig(0x700);

    sched_main();
}
