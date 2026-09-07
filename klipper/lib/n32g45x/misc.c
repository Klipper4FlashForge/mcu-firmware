// Nations N32G45x standard peripheral library - NVIC (misc) driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"
#include "n32g45x_internal.h"


void
NVIC_PriorityGroupConfig(uint32_t NVIC_PriorityGroup)
{
    NS_SCB->AIRCR = AIRCR_VECTKEY_MASK | NVIC_PriorityGroup;
}

void
NVIC_Init(NVIC_InitType *NVIC_InitStruct)
{
    uint32_t tmppriority = 0x00, tmppre = 0x00, tmpsub = 0x0f;

    if (NVIC_InitStruct->NVIC_IRQChannelCmd != DISABLE) {
        // Compute the Corresponding IRQ Priority
        tmppriority = (0x700 - (NS_SCB->AIRCR & (uint32_t)0x700)) >> 0x08;
        tmppre = (0x4 - tmppriority);
        tmpsub = tmpsub >> tmppriority;

        tmppriority = (uint32_t)NVIC_InitStruct
            ->NVIC_IRQChannelPreemptionPriority << tmppre;
        tmppriority |= NVIC_InitStruct->NVIC_IRQChannelSubPriority & tmpsub;
        tmppriority = tmppriority << 0x04;

        NS_NVIC->IP[NVIC_InitStruct->NVIC_IRQChannel] = tmppriority;

        // Enable the Selected IRQ Channels
        NS_NVIC->ISER[NVIC_InitStruct->NVIC_IRQChannel >> 0x05] =
            (uint32_t)0x01 << (NVIC_InitStruct->NVIC_IRQChannel & (uint8_t)0x1f);
    } else {
        // Disable the Selected IRQ Channels
        NS_NVIC->ICER[NVIC_InitStruct->NVIC_IRQChannel >> 0x05] =
            (uint32_t)0x01 << (NVIC_InitStruct->NVIC_IRQChannel & (uint8_t)0x1f);
    }
}
