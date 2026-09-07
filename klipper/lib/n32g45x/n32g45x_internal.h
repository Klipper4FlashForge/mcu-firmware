// Private definitions shared by the N32G45x peripheral driver modules.
//
// The Cortex-M core blocks and the RCC clock-control registers are used by
// more than one module here but are not part of the public driver API, so
// they live in this header rather than in n32g45x.h.

#ifndef N32G45X_INTERNAL_H
#define N32G45X_INTERNAL_H

#include <stdint.h>
#include "n32g45x.h"

typedef struct
{
    __IO uint32_t ISER[8];
    uint32_t RESERVED0[24];
    __IO uint32_t ICER[8];
    uint32_t RSERVED1[24];
    __IO uint32_t ISPR[8];
    uint32_t RESERVED2[24];
    __IO uint32_t ICPR[8];
    uint32_t RESERVED3[24];
    __IO uint32_t IABR[8];
    uint32_t RESERVED4[56];
    __IO uint8_t IP[240];
} NVIC_Type;

typedef struct
{
    __IO uint32_t CPUID;
    __IO uint32_t ICSR;
    __IO uint32_t VTOR;
    __IO uint32_t AIRCR;
} SCB_Type;

#define NS_NVIC ((NVIC_Type *)0xe000e100)
#define NS_SCB  ((SCB_Type *)0xe000ed00)

#define AIRCR_VECTKEY_MASK ((uint32_t)0x05fa0000)

#define RCC_BASE      0x40021000
#define RCC_CFG       (*(__IO uint32_t *)(RCC_BASE + 0x04))
#define RCC_AHBPCLKEN (*(__IO uint32_t *)(RCC_BASE + 0x14))
#define RCC_APB2PCLKEN (*(__IO uint32_t *)(RCC_BASE + 0x18))

#endif // n32g45x_internal.h
