// Nations N32G45x standard peripheral library - subset used by the
// FlashForge levelBoard firmware.  Reconstructed from the stock image.
//
// Function order below matches stock's own layout (misc -> gpio -> usart ->
// rcc -> tim -> dma, SDK definition order within each), read off the image
// at 0x08008924-0x08009044 via relocmap.py/armdis.py.  GCC 10.3 at -O2 with
// -ffunction-sections places .text.<fn> sections in link order, and the
// linker keeps input-file order, so source order here drives image order.

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


/****************************************************************
 * NVIC (misc)
 ****************************************************************/

__attribute__((no_reorder))
void
NVIC_PriorityGroupConfig(uint32_t NVIC_PriorityGroup)
{
    NS_SCB->AIRCR = AIRCR_VECTKEY_MASK | NVIC_PriorityGroup;
}

__attribute__((no_reorder))
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


/****************************************************************
 * GPIO
 ****************************************************************/

__attribute__((no_reorder))
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

__attribute__((no_reorder))
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

__attribute__((no_reorder))
void
GPIO_InitPeripheral(GPIO_Module *GPIOx, GPIO_InitType *GPIO_InitStruct)
{
    // No early return for an empty pin mask: the loop guard handles it, and
    // an explicit return in front of it changes GCC's block layout.
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

__attribute__((no_reorder))
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

__attribute__((no_reorder))
void
GPIO_SetBits(GPIO_Module *GPIOx, uint32_t pin)
{
    GPIOx->PBSC = pin;
}


/****************************************************************
 * USART
 ****************************************************************/

__attribute__((no_reorder))
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

__attribute__((no_reorder))
void
USART_Init(USART_Module *USARTx, USART_InitType *USART_InitStruct)
{
    USART_ConfigBaudRate(USARTx, USART_InitStruct->BaudRate);

    uint32_t tmpreg = USARTx->CTRL1;
    tmpreg &= ~((uint16_t)0x1000);
    tmpreg |= USART_InitStruct->WordLength;
    USARTx->CTRL1 = tmpreg;

    tmpreg = USARTx->CTRL2;
    tmpreg &= ~((uint16_t)0x3000);
    tmpreg |= USART_InitStruct->StopBits;
    USARTx->CTRL2 = tmpreg;

    tmpreg = USARTx->CTRL1;
    tmpreg &= ~((uint16_t)0x0600);
    tmpreg |= USART_InitStruct->Parity;
    USARTx->CTRL1 = tmpreg;

    tmpreg = USARTx->CTRL1;
    tmpreg &= ~((uint16_t)0x000c);
    tmpreg |= USART_InitStruct->Mode;
    USARTx->CTRL1 = tmpreg;

    tmpreg = USARTx->CTRL3;
    tmpreg &= ~((uint16_t)0x0300);
    tmpreg |= USART_InitStruct->HardwareFlowControl;
    USARTx->CTRL3 = tmpreg;
}

__attribute__((no_reorder))
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

__attribute__((no_reorder))
void
USART_Enable(USART_Module *USARTx)
{
    USARTx->CTRL1 |= USART_CTRL1_UEN;
}

__attribute__((no_reorder))
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

__attribute__((no_reorder))
void
USART_ClrFlag(USART_Module *USARTx, uint16_t USART_FLAG)
{
    USARTx->STS = (uint16_t)~USART_FLAG;
}


/****************************************************************
 * RCC
 ****************************************************************/

// APB/AHB prescaler tables (stock image: 0x0800a7ec / 0x0800a7bc / 0x0800a7cc)
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

__attribute__((no_reorder))
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
        // Stock halves HSI only when RCC+0x40 bit 0 is set. The published
        // SDK halves it unconditionally; this conditional is the single
        // difference between FlashForge's driver and every public copy.
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

__attribute__((no_reorder))
void
RCC_EnableAHBPeriphClk(uint32_t RCC_AHBPeriph)
{
    RCC_AHBPeriph |= RCC_AHBPCLKEN;
    RCC_AHBPCLKEN = RCC_AHBPeriph;
}

__attribute__((no_reorder))
void
RCC_EnableAPB2PeriphClk(uint32_t RCC_APB2Periph)
{
    RCC_APB2Periph |= RCC_APB2PCLKEN;
    RCC_APB2PCLKEN = RCC_APB2Periph;
}


/****************************************************************
 * TIM
 ****************************************************************/

__attribute__((no_reorder))
void
TIM_SetEventGeneration(TIM_Module *TIMx, uint16_t value)
{
    TIMx->EGR = value;
}

__attribute__((noipa, no_reorder)) void
TIM_InitTimeBase(TIM_Module *TIMx, TIM_TimeBaseInitType *s)
{
    // This is the stock driver's complete decision tree.  TIM6 uses the
    // reduced basic-timer path; the other instances configure the common
    // counter fields and the capture-input selectors supported by that
    // particular timer.  The basic-timer path is the else branch rather
    // than an early return: that is what places its code last, as in stock.
    if (TIMx != NS_TIM6) {
        uint32_t tmp = TIMx->CR1;
        tmp &= ~((uint32_t)0x0070);
        tmp |= s->CntMode;
        TIMx->CR1 = tmp;

        tmp = TIMx->CR1;
        tmp &= ~((uint32_t)0x0300);
        TIMx->CR1 = tmp;
        TIMx->CR1 |= s->ClkDiv;

        TIMx->ARR = s->Period;
        TIMx->PSC = s->Prescaler;
        // Stock's compiler saw the TIM8 test at even odds.  GCC 10 predicts
        // a pointer equality as 30 % taken, and that guess alone changes the
        // block layout; the weight below restores stock's layout.  The
        // spelling FlashForge used to get there is not known.
        if (TIMx == NS_TIM1
            || __builtin_expect_with_probability(TIMx == NS_TIM8, 1, 0.5))
            TIMx->RCR = s->RepetCnt;
        TIMx->EGR = 1;

        if (!s->CapCh1FromCompEn)
            TIMx->CR1 &= ~((uint32_t)0x0800);
        else
            TIMx->CR1 |= 0x0800;

        if (TIMx != NS_TIM1 && TIMx != NS_TIM8 && TIMx != NS_TIM2
            && TIMx != NS_TIM3 && TIMx != NS_TIM4)
            return;
        if (s->CapEtrClrFromCompEn)
            TIMx->CR1 |= 0x8000;
        else
            TIMx->CR1 &= ~((uint32_t)0x8000);

        if (TIMx != NS_TIM2)
            return;
        if (s->CapCh2FromCompEn)
            TIMx->CR1 |= 0x1000;
        else
            TIMx->CR1 &= ~((uint32_t)0x1000);
        if (s->CapCh3FromCompEn)
            TIMx->CR1 |= 0x2000;
        else
            TIMx->CR1 &= ~((uint32_t)0x2000);
        if (s->CapCh4FromCompEn)
            TIMx->CR1 |= 0x4000;
        else
            TIMx->CR1 &= ~((uint32_t)0x4000);
    } else {
        TIMx->ARR = s->Period;
        TIMx->PSC = s->Prescaler;
        TIMx->EGR = 1;
    }
}

__attribute__((noipa, no_reorder)) void
TIM_InitTimBaseStruct(TIM_TimeBaseInitType *s)
{
    s->Period = 0xffff;
    s->Prescaler = 0;
    s->ClkDiv = 0;
    s->CntMode = 0;
    s->RepetCnt = 0;
    s->CapCh1FromCompEn = 0;
    s->CapCh2FromCompEn = 0;
    s->CapCh3FromCompEn = 0;
    s->CapCh4FromCompEn = 0;
    s->CapEtrClrFromCompEn = 0;
    s->CapEtrSelFromTscEn = 0;
}

__attribute__((no_reorder))
void
TIM_Cmd(TIM_Module *TIMx)
{
    // The levelBoard only calls this helper with ENABLE.  Stock's vendor
    // implementation is the enable-only four-instruction sequence.
    TIMx->CR1 |= 1;
}

__attribute__((no_reorder))
void
TIM_ETRClockMode2Config(TIM_Module *TIMx, uint16_t prescaler,
                        uint16_t polarity, uint16_t filter)
{
    // The prescaler is copied into a local before anything else so that
    // its SSA name is numbered before the register temporaries.  GCC
    // orders the operands of a commutative operation by SSA version, and
    // the two-operand Thumb orrs takes its destination from the first
    // operand: this is what puts the final orr into r1 (the prescaler's
    // register) at 0x08008E4C instead of r3.
    uint16_t psc = prescaler;
    uint16_t tmp = TIMx->SMCR;
    tmp &= (uint16_t)~0x0f00;
    tmp |= (uint16_t)(filter << 8);
    TIMx->SMCR = tmp;
    // Each arm stores the register itself; merging the arms into one
    // value lets GCC fold the set into an orr, where stock keeps the
    // shift-and-complement form.
    if (polarity == 0x8000)
        TIMx->SMCR |= 0x8000;
    else
        TIMx->SMCR &= (uint16_t)~0x8000;
    tmp = TIMx->SMCR;
    tmp &= (uint16_t)~0x3000;
    tmp |= psc;
    TIMx->SMCR = tmp;
    TIMx->SMCR = (uint16_t)(TIMx->SMCR | 0x4000);
}

__attribute__((no_reorder))
void
TIM_DMACmd(TIM_Module *TIMx, uint16_t request)
{
    TIMx->DIER = (uint16_t)(TIMx->DIER | request);
}

static TIM_TimeBaseInitType TIM_TimeBaseInitStructure;

__attribute__((no_reorder))
void
TIM_TimeBaseInit(TIM_Module *TIMx, uint16_t period, uint16_t prescaler)
{
    TIM_InitTimBaseStruct(&TIM_TimeBaseInitStructure);
    TIM_TimeBaseInitStructure.Period = period;
    TIM_TimeBaseInitStructure.Prescaler = prescaler;
    TIM_TimeBaseInitStructure.ClkDiv = 0;
    TIM_TimeBaseInitStructure.CntMode = 0;
    TIM_InitTimeBase(TIMx, &TIM_TimeBaseInitStructure);
}


/****************************************************************
 * DMA
 ****************************************************************/

__attribute__((no_reorder))
void
DMA_DeInit(DMA_ChannelType *channel)
{
    channel->CHCFG &= ~((uint32_t)0x1);
    channel->CHCFG = 0;
    channel->TXNUM = 0;
    channel->PADDR = 0;
    channel->MADDR = 0;
    if (channel == NS_DMA1_CH1)
        NS_DMA1->INTCLR |= (uint32_t)0x0000000f;
    else if (channel == NS_DMA1_CH2)
        NS_DMA1->INTCLR |= (uint32_t)0x000000f0;
    else if (channel == NS_DMA1_CH3)
        NS_DMA1->INTCLR |= (uint32_t)0x00000f00;
    else if (channel == NS_DMA1_CH4)
        NS_DMA1->INTCLR |= (uint32_t)0x0000f000;
    else if (channel == NS_DMA1_CH5)
        NS_DMA1->INTCLR |= (uint32_t)0x000f0000;
    else if (channel == NS_DMA1_CH6)
        NS_DMA1->INTCLR |= (uint32_t)0x00f00000;
    else if (channel == NS_DMA1_CH7)
        NS_DMA1->INTCLR |= (uint32_t)0x0f000000;
    else if (channel == NS_DMA1_CH8)
        NS_DMA1->INTCLR |= (uint32_t)0xf0000000;
}

__attribute__((no_reorder))
void
DMA_Init(DMA_ChannelType *channel, DMA_InitType *DMA_InitParam)
{
    channel->PADDR = DMA_InitParam->PeriphAddr;
    channel->MADDR = DMA_InitParam->MemAddr;

    // Every configuration field is applied as its own read-clear-write
    // followed by a separate read-set-write of the channel config register,
    // which is what puts a paired bic/orr around each field in the image.
    //
    // Each field is read one group ahead of the field it configures, and the
    // locals are int: the signed intermediate keeps a conversion of its own in
    // the tree, which is what fixes the order IRA colours the fields in and so
    // holds the working set to three fields and {r4, r5}.
    int dir = DMA_InitParam->Direction;
    channel->CHCFG &= ~((uint32_t)0x0010);
    channel->CHCFG |= dir;
    int bufsize = DMA_InitParam->BufSize;
    if (channel) {
        channel->TXNUM = bufsize;
    } else {
        channel->TXNUM = bufsize;
    }
    int pinc = DMA_InitParam->PeriphInc;
    channel->CHCFG &= ~((uint32_t)0x0040);
    channel->CHCFG |= pinc;
    int minc = DMA_InitParam->DMA_MemoryInc;
    channel->CHCFG &= ~((uint32_t)0x0080);
    channel->CHCFG |= minc;
    int psize = DMA_InitParam->PeriphDataSize;
    channel->CHCFG &= ~((uint32_t)0x0300);
    channel->CHCFG |= psize;
    int msize = DMA_InitParam->MemDataSize;
    channel->CHCFG &= ~((uint32_t)0x0c00);
    channel->CHCFG |= msize;
    int circ = DMA_InitParam->CircularMode;
    int prio = DMA_InitParam->Priority;
    channel->CHCFG &= ~((uint32_t)0x0020);
    int m2m = DMA_InitParam->Mem2Mem;
    channel->CHCFG |= circ;
    channel->CHCFG &= ~((uint32_t)0x3000);
    channel->CHCFG |= prio;
    channel->CHCFG &= ~((uint32_t)0x4000);
    channel->CHCFG |= m2m;
}

__attribute__((no_reorder))
void
DMA_EnableChannel(DMA_ChannelType *channel)
{
    channel->CHCFG |= (uint32_t)0x0001;
}

__attribute__((no_reorder))
void
DMA_DisableChannel(DMA_ChannelType *channel)
{
    channel->CHCFG &= ~((uint32_t)0x0001);
}

__attribute__((no_reorder))
void
DMA_ConfigInt(DMA_ChannelType *channel, uint32_t DMA_INT)
{
    channel->CHCFG |= DMA_INT;
}

// DMA_GetIntStatus and DMA_GetFlagStatus are the same function twice, and
// GCC's identical-code folding is what makes stock's two copies differ:
// the second one comes out with the tst operands swapped.  Which copy a
// handler calls is therefore visible in the image: channel 5 uses the
// interrupt pair, channels 1 and 4 the flag pair.
__attribute__((no_reorder))
uint32_t
DMA_GetIntStatus(DMA_Module *DMAy, uint32_t DMAy_INT)
{
    return (DMAy_INT & DMAy->INTSTS) ? 1 : 0;
}

__attribute__((no_reorder))
void
DMA_ClrIntPendingBit(DMA_Module *DMAy, uint32_t DMAy_INT)
{
    DMAy->INTCLR = DMAy_INT;
}

__attribute__((no_reorder))
uint32_t
DMA_GetFlagStatus(DMA_Module *DMAy, uint32_t DMAy_FLAG)
{
    return (DMAy->INTSTS & DMAy_FLAG) ? 1 : 0;
}

__attribute__((no_reorder))
void
DMA_ClearFlag(DMA_Module *DMAy, uint32_t DMAy_FLAG)
{
    DMAy->INTCLR = DMAy_FLAG;
}

__attribute__((no_reorder))
void
DMA_RequestRemap(DMA_ChannelType *channel, uint32_t remap)
{
    channel->CHSEL = remap;
}
