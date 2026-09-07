// Nations N32G45x standard peripheral library - GPIO driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"


void
GPIO_ConfigPinAF(GPIO_Module *GPIOx, uint32_t af, uint32_t pinpos)
{
    uint32_t tmp;
    if (pinpos & 0x08) {
        tmp = GPIOx->AFH;
        tmp &= ~(0x0ful << ((pinpos & 0x07) * 4));
        tmp |= af << ((pinpos & 0x07) * 4);
        GPIOx->AFH = tmp;
    } else {
        tmp = GPIOx->AFL;
        tmp &= ~(0x0ful << ((pinpos & 0x07) * 4));
        tmp |= af << ((pinpos & 0x07) * 4);
        GPIOx->AFL = tmp;
    }
}

void
GPIO_ConfigPinMode(GPIO_Module *GPIOx, uint32_t mode, uint32_t pinpos)
{
    uint32_t tmp = GPIOx->PMODE;
    tmp &= ~(0x03ul << (pinpos * 2));
    tmp |= (mode & 0x03ul) << (pinpos * 2);
    GPIOx->PMODE = tmp;

    uint32_t base = mode & ~0x10ul;
    if (base == GPIO_MODE_OUT_PP || base == GPIO_MODE_AF_PP) {
        tmp = GPIOx->POTYPE;
        tmp &= ~(0x01ul << pinpos);
        tmp |= ((mode >> 4) & 0x01ul) << pinpos;
        GPIOx->POTYPE = tmp;
    }
}

void
GPIO_InitPeripheral(GPIO_Module *GPIOx, GPIO_InitType *GPIO_InitStruct)
{
    uint32_t pins = GPIO_InitStruct->Pin;
    uint32_t pinpos = 0;
    while (pins >> pinpos) {
        uint32_t currentpin = 0x01ul << pinpos;
        if (pins & currentpin) {
            GPIO_ConfigPinAF(GPIOx, GPIO_InitStruct->GPIO_Alternate, pinpos);
            GPIO_ConfigPinMode(GPIOx, GPIO_InitStruct->GPIO_Mode, pinpos);

            uint32_t tmp = GPIOx->PUPD;
            tmp &= ~(0x03ul << (pinpos * 2));
            tmp |= GPIO_InitStruct->GPIO_Pull << (pinpos * 2);
            GPIOx->PUPD = tmp;

            tmp = GPIOx->SR;
            tmp &= ~currentpin;
            tmp |= GPIO_InitStruct->GPIO_Slew_Rate << pinpos;
            GPIOx->SR = tmp;

            tmp = GPIOx->DS;
            tmp &= ~(0x03ul << (pinpos * 2));
            tmp |= GPIO_InitStruct->GPIO_Current << (pinpos * 2);
            GPIOx->DS = tmp;

            pins = GPIO_InitStruct->Pin;
        }
        pinpos++;
    }
}

void
GPIO_InitStruct(GPIO_InitType *GPIO_InitStruct)
{
    GPIO_InitStruct->Pin = GPIO_PIN_ALL;
    GPIO_InitStruct->GPIO_Slew_Rate = GPIO_SLEW_RATE_FAST;
    GPIO_InitStruct->GPIO_Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct->GPIO_Alternate = GPIO_NO_AF;
    GPIO_InitStruct->GPIO_Pull = GPIO_NO_PULL;
    GPIO_InitStruct->GPIO_Current = GPIO_DC_2MA;
}

void
GPIO_SetBits(GPIO_Module *GPIOx, uint32_t pin)
{
    GPIOx->PBSC = pin;
}
