// Nations N32G45x standard peripheral library - RCC driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"
#include "n32g45x_internal.h"


// APB/AHB and ADC clock prescaler tables
static const uint8_t APBAHBPresTable[16] = {
    0, 0, 0, 0, 1, 2, 3, 4, 1, 2, 3, 4, 6, 7, 8, 9
};
static const uint8_t ADCHCLKPresTable[16] = {
    1, 2, 4, 6, 8, 10, 12, 16, 32, 32, 32, 32, 32, 32, 32, 32
};
static const uint16_t ADCPLLCLKPresTable[16] = {
    1, 2, 4, 6, 8, 10, 12, 16, 32, 64, 128, 256, 256, 256, 256, 256
};

#define HSI_VALUE 8000000
#define HSE_VALUE 8000000
#define CFG_PLLMULFCT_MASK      ((uint32_t)0x083C0000)
#define CFG_PLLSRC_MASK         ((uint32_t)0x00010000)
#define CFG_PLLHSEPRES_MASK     ((uint32_t)0x00020000)
#define CFG_SCLKSTS_MASK        ((uint32_t)0x0000000C)
#define CFG_AHBPRES_SET_MASK    ((uint32_t)0x000000F0)
#define CFG_APB1PRES_SET_MASK   ((uint32_t)0x00000700)
#define CFG_APB2PRES_SET_MASK   ((uint32_t)0x00003800)
#define CFG2_ADCPLLPRES_SET_MASK ((uint32_t)0x000001F0)
#define CFG2_ADCHPRES_SET_MASK  ((uint32_t)0x0000000F)
#define RCC_CFG_PLLMULFCT_4     ((uint32_t)0x08000000)
#define RCC_PLLHSIPRE (*(__IO uint32_t *)(RCC_BASE + 0x40))
#define RCC_CFG2      (*(__IO uint32_t *)(RCC_BASE + 0x2c))

void
RCC_GetClocksFreqValue(RCC_ClocksType *RCC_Clocks)
{
    uint32_t tmp = 0, pllclk = 0, pllmull = 0, pllsource = 0, presc = 0;

    // PLL clock source and multiplication factor
    pllmull = RCC_CFG & CFG_PLLMULFCT_MASK;
    pllsource = RCC_CFG & CFG_PLLSRC_MASK;

    if ((pllmull & RCC_CFG_PLLMULFCT_4) == 0)
        pllmull = (pllmull >> 18) + 2;          // PLLMUL[4]=0
    else
        pllmull = ((pllmull >> 18) - 496) + 1;  // PLLMUL[4]=1

    if (pllsource == 0x00) {
        // The HSI feeds the PLL through a divider that this part can
        // bypass, so halve it only when PLLHSIPRE says so.  The published
        // SDK halves it unconditionally and gets the clock wrong here.
        if ((RCC_PLLHSIPRE & 0x00000001) != 0)
            pllclk = (HSI_VALUE >> 1) * pllmull;
        else
            pllclk = HSI_VALUE * pllmull;
    } else {
        if ((RCC_CFG & CFG_PLLHSEPRES_MASK) != 0)
            pllclk = (HSE_VALUE >> 1) * pllmull;
        else
            pllclk = HSE_VALUE * pllmull;
    }

    // SYSCLK source
    tmp = RCC_CFG & CFG_SCLKSTS_MASK;
    switch (tmp) {
    case 0x00:
        RCC_Clocks->SysclkFreq = HSI_VALUE;
        break;
    case 0x04:
        RCC_Clocks->SysclkFreq = HSE_VALUE;
        break;
    case 0x08:
        RCC_Clocks->SysclkFreq = pllclk;
        break;
    default:
        RCC_Clocks->SysclkFreq = HSI_VALUE;
        break;
    }

    tmp = RCC_CFG & CFG_AHBPRES_SET_MASK;
    tmp = tmp >> 4;
    presc = APBAHBPresTable[tmp];
    RCC_Clocks->HclkFreq = RCC_Clocks->SysclkFreq >> presc;

    tmp = RCC_CFG & CFG_APB1PRES_SET_MASK;
    tmp = tmp >> 8;
    presc = APBAHBPresTable[tmp];
    RCC_Clocks->Pclk1Freq = RCC_Clocks->HclkFreq >> presc;

    tmp = RCC_CFG & CFG_APB2PRES_SET_MASK;
    tmp = tmp >> 11;
    presc = APBAHBPresTable[tmp];
    RCC_Clocks->Pclk2Freq = RCC_Clocks->HclkFreq >> presc;

    tmp = RCC_CFG2 & CFG2_ADCHPRES_SET_MASK;
    presc = ADCHCLKPresTable[tmp];
    RCC_Clocks->AdcHclkFreq = RCC_Clocks->HclkFreq / presc;

    tmp = RCC_CFG2 & CFG2_ADCPLLPRES_SET_MASK;
    tmp = tmp >> 4;
    presc = ADCPLLCLKPresTable[(tmp & 0xF)];    // ignore BIT5
    RCC_Clocks->AdcPllClkFreq = pllclk / presc;
}

void
RCC_EnableAHBPeriphClk(uint32_t RCC_AHBPeriph)
{
    RCC_AHBPeriph |= RCC_AHBPCLKEN;
    RCC_AHBPCLKEN = RCC_AHBPeriph;
}

void
RCC_EnableAPB2PeriphClk(uint32_t RCC_APB2Periph)
{
    RCC_APB2Periph |= RCC_APB2PCLKEN;
    RCC_APB2PCLKEN = RCC_APB2Periph;
}
