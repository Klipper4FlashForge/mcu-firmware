// Nations N32G45x standard peripheral library - USART driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"


void
USART_ConfigBaudRate(USART_Module *USARTx, uint32_t baud)
{
    RCC_ClocksType RCC_ClocksStatus;
    uint32_t apbclock, integerdivider, fractionaldivider;

    RCC_GetClocksFreqValue(&RCC_ClocksStatus);
    if (USARTx == NS_USART1 || USARTx == NS_UART6 || USARTx == NS_UART7)
        apbclock = RCC_ClocksStatus.Pclk2Freq;
    else
        apbclock = RCC_ClocksStatus.Pclk1Freq;

    // Determine the integer part
    integerdivider = (25 * apbclock) / (4 * baud);
    uint32_t tmpreg = (integerdivider / 100) << 4;

    // Determine the fractional part
    fractionaldivider = integerdivider - (100 * (tmpreg >> 4));
    tmpreg |= ((((fractionaldivider * 16) + 50) / 100)) & ((uint8_t)0x0f);

    USARTx->BRCF = (uint16_t)tmpreg;
}

void
USART_Init(USART_Module *USARTx, USART_InitType *USART_InitStruct)
{
    USART_ConfigBaudRate(USARTx, USART_InitStruct->BaudRate);

    uint32_t tmpreg = USARTx->CTRL1;
    tmpreg &= ~USART_CTRL1_WL_MASK;
    tmpreg |= USART_InitStruct->WordLength;
    USARTx->CTRL1 = tmpreg;

    tmpreg = USARTx->CTRL2;
    tmpreg &= ~USART_CTRL2_STPB_MASK;
    tmpreg |= USART_InitStruct->StopBits;
    USARTx->CTRL2 = tmpreg;

    tmpreg = USARTx->CTRL1;
    tmpreg &= ~USART_CTRL1_PARITY_MASK;
    tmpreg |= USART_InitStruct->Parity;
    USARTx->CTRL1 = tmpreg;

    tmpreg = USARTx->CTRL1;
    tmpreg &= ~USART_CTRL1_MODE_MASK;
    tmpreg |= USART_InitStruct->Mode;
    USARTx->CTRL1 = tmpreg;

    tmpreg = USARTx->CTRL3;
    tmpreg &= ~USART_CTRL3_HFCTRL_MASK;
    tmpreg |= USART_InitStruct->HardwareFlowControl;
    USARTx->CTRL3 = tmpreg;
}

void
USART_StructInit(USART_InitType *USART_InitStruct)
{
    USART_InitStruct->BaudRate = 9600;
    USART_InitStruct->WordLength = USART_WL_8B;
    USART_InitStruct->StopBits = USART_STPB_1;
    USART_InitStruct->Parity = USART_PE_NO;
    USART_InitStruct->Mode = USART_MODE_RX | USART_MODE_TX;
    USART_InitStruct->HardwareFlowControl = USART_HFCTRL_NONE;
}

void
USART_Enable(USART_Module *USARTx)
{
    USARTx->CTRL1 |= USART_CTRL1_UEN;
}

void
USART_ConfigInt(USART_Module *USARTx, uint16_t USART_INT)
{
    uint32_t usartxbase = (uint32_t)USARTx;
    uint32_t usartreg = (((uint8_t)USART_INT) >> 0x05);
    uint32_t itpos = USART_INT & ((uint16_t)0x001f);
    uint32_t itmask = ((uint32_t)0x01) << itpos;

    if (usartreg == 0x01)
        usartxbase += 0x0c;
    else if (usartreg == 0x02)
        usartxbase += 0x10;
    else
        usartxbase += 0x14;
    *(__IO uint32_t *)usartxbase |= itmask;
}

void
USART_ClrFlag(USART_Module *USARTx, uint16_t USART_FLAG)
{
    USARTx->STS = (uint16_t)~USART_FLAG;
}
