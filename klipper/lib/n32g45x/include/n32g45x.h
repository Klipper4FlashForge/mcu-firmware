// Minimal Nations N32G45x peripheral library definitions
//
// Register layouts and constants recovered from the FlashForge levelBoard
// firmware image.  Names follow the Nations N32G45x standard peripheral
// library.  Everything is prefixed NS_ so it cannot collide with the CMSIS
// stm32f103xe.h definitions that Klipper's stm32 port pulls in.

#ifndef __N32G45x_H
#define __N32G45x_H

#include <stdbool.h>
#include <stdint.h>

#define __IO volatile

// The CMSIS stm32f1xx.h that Klipper's stm32 port pulls in already declares
// this identical enum; only declare it when that header is not in play.
#ifndef IS_FUNCTIONAL_STATE
typedef enum {DISABLE = 0, ENABLE = !DISABLE} FunctionalState;
#endif

// ---------------------------------------------------------------- GPIO ----

typedef struct
{
    __IO uint32_t PMODE;        // 0x00 pin mode, 2 bits per pin
    __IO uint32_t POTYPE;       // 0x04 output type, 1 bit per pin
    __IO uint32_t SR;           // 0x08 slew rate, 1 bit per pin
    __IO uint32_t PUPD;         // 0x0c pull up/down, 2 bits per pin
    __IO uint32_t PID;          // 0x10 input data
    __IO uint32_t POD;          // 0x14 output data
    __IO uint32_t PBSC;         // 0x18 bit set/clear
    __IO uint32_t PLOCK;        // 0x1c
    __IO uint32_t AFL;          // 0x20 alt function, pins 0-7
    __IO uint32_t AFH;          // 0x24 alt function, pins 8-15
    __IO uint32_t PBC;          // 0x28 bit clear
    __IO uint32_t DS;           // 0x2c drive current, 2 bits per pin
} GPIO_Module;

typedef struct
{
    uint32_t Pin;               // 0x00
    uint32_t GPIO_Mode;         // 0x04
    uint32_t GPIO_Pull;         // 0x08
    uint32_t GPIO_Slew_Rate;    // 0x0c
    uint32_t GPIO_Current;      // 0x10
    uint32_t GPIO_Alternate;    // 0x14
} GPIO_InitType;

#define NS_GPIOA ((GPIO_Module *)0x40023400)
#define NS_GPIOB ((GPIO_Module *)0x40023800)
#define NS_GPIOC ((GPIO_Module *)0x40023c00)
#define NS_GPIOD ((GPIO_Module *)0x40024000)

#define GPIO_PIN_ALL    ((uint32_t)0xffff)
#define GPIO_PIN_9      ((uint32_t)0x0200)
#define GPIO_PIN_10     ((uint32_t)0x0400)

#define GPIO_MODE_INPUT     ((uint32_t)0x00)
#define GPIO_MODE_OUT_PP    ((uint32_t)0x01)
#define GPIO_MODE_AF_PP     ((uint32_t)0x02)
#define GPIO_MODE_ANALOG    ((uint32_t)0x03)
#define GPIO_MODE_OUT_OD    ((uint32_t)0x11)
#define GPIO_MODE_AF_OD     ((uint32_t)0x12)

#define GPIO_NO_PULL        ((uint32_t)0x00)
#define GPIO_PULL_UP        ((uint32_t)0x01)
#define GPIO_PULL_DOWN      ((uint32_t)0x02)

#define GPIO_SLEW_RATE_FAST ((uint32_t)0x00)
#define GPIO_DC_2MA         ((uint32_t)0x00)

#define GPIO_NO_AF          ((uint32_t)0x0f)
#define GPIO_AF5_USART1     ((uint32_t)0x05)

void GPIO_ConfigPinAF(GPIO_Module *GPIOx, uint32_t af, uint32_t pinpos);
void GPIO_ConfigPinMode(GPIO_Module *GPIOx, uint32_t mode, uint32_t pinpos);
void GPIO_InitStruct(GPIO_InitType *GPIO_InitStruct);
void GPIO_InitPeripheral(GPIO_Module *GPIOx, GPIO_InitType *GPIO_InitStruct);
void GPIO_SetBits(GPIO_Module *GPIOx, uint32_t pin);

// --------------------------------------------------------------- USART ----

// Note: every USART register is accessed 16 bits wide by the stock firmware
typedef struct
{
    __IO uint16_t STS;          // 0x00 status
    uint16_t RESERVED0;
    __IO uint16_t DAT;          // 0x04 data
    uint16_t RESERVED1;
    __IO uint16_t BRCF;         // 0x08 baud rate
    uint16_t RESERVED2;
    __IO uint16_t CTRL1;        // 0x0c
    uint16_t RESERVED3;
    __IO uint16_t CTRL2;        // 0x10
    uint16_t RESERVED4;
    __IO uint16_t CTRL3;        // 0x14
    uint16_t RESERVED5;
    __IO uint16_t GTP;          // 0x18
    uint16_t RESERVED6;
} USART_Module;

typedef struct
{
    uint32_t BaudRate;          // 0x00
    uint16_t WordLength;        // 0x04
    uint16_t StopBits;          // 0x06
    uint16_t Parity;            // 0x08
    uint16_t Mode;              // 0x0a
    uint16_t HardwareFlowControl; // 0x0c
} USART_InitType;

#define NS_USART1 ((USART_Module *)0x40013800)
#define NS_USART2 ((USART_Module *)0x40004400)
#define NS_USART3 ((USART_Module *)0x40004800)
#define NS_UART6  ((USART_Module *)0x40015000)
#define NS_UART7  ((USART_Module *)0x40015400)

#define USART_STS_PEF       ((uint16_t)0x0001)
#define USART_STS_FEF       ((uint16_t)0x0002)
#define USART_STS_NEF       ((uint16_t)0x0004)
#define USART_STS_OREF      ((uint16_t)0x0008)
#define USART_STS_IDLEF     ((uint16_t)0x0010)
#define USART_STS_RXDNE     ((uint16_t)0x0020)
#define USART_STS_TXC       ((uint16_t)0x0040)
#define USART_STS_TXDE      ((uint16_t)0x0080)

#define USART_CTRL1_RXDNEIEN ((uint16_t)0x0020)
#define USART_CTRL1_TXDEIEN  ((uint16_t)0x0080)
#define USART_CTRL1_REN      ((uint16_t)0x0004)
#define USART_CTRL1_TEN      ((uint16_t)0x0008)
#define USART_CTRL1_UEN      ((uint16_t)0x2000)

#define USART_WL_8B         ((uint16_t)0x0000)
#define USART_STPB_1        ((uint16_t)0x0000)
#define USART_PE_NO         ((uint16_t)0x0000)
#define USART_MODE_RX       ((uint16_t)0x0004)
#define USART_MODE_TX       ((uint16_t)0x0008)
#define USART_HFCTRL_NONE   ((uint16_t)0x0000)

#define USART_FLAG_TXC      ((uint16_t)0x0040)
// interrupt id: (control register index << 5) | bit position
#define USART_INT_RXDNE     ((uint16_t)0x0525)

void USART_Init(USART_Module *USARTx, USART_InitType *USART_InitStruct);
void USART_StructInit(USART_InitType *USART_InitStruct);
void USART_ConfigBaudRate(USART_Module *USARTx, uint32_t baud);
void USART_Enable(USART_Module *USARTx);
void USART_ConfigInt(USART_Module *USARTx, uint16_t USART_INT);
void USART_ClrFlag(USART_Module *USARTx, uint16_t USART_FLAG);

// ----------------------------------------------------------------- DMA ----

typedef struct
{
    __IO uint32_t CHCFG;        // 0x00
    __IO uint32_t TXNUM;        // 0x04
    __IO uint32_t PADDR;        // 0x08
    __IO uint32_t MADDR;        // 0x0c
    __IO uint32_t CHSEL;        // 0x10 request remap
} DMA_ChannelType;

typedef struct
{
    __IO uint32_t INTSTS;       // 0x00
    __IO uint32_t INTCLR;       // 0x04
} DMA_Module;

typedef struct
{
    uint32_t PeriphAddr;        // 0x00
    uint32_t MemAddr;           // 0x04
    uint32_t Direction;         // 0x08
    uint32_t BufSize;           // 0x0c
    uint32_t PeriphInc;         // 0x10
    uint32_t DMA_MemoryInc;     // 0x14
    uint32_t PeriphDataSize;    // 0x18
    uint32_t MemDataSize;       // 0x1c
    uint32_t CircularMode;      // 0x20
    uint32_t Priority;          // 0x24
    uint32_t Mem2Mem;           // 0x28
} DMA_InitType;

#define NS_DMA1     ((DMA_Module *)0x40020000)
#define NS_DMA1_CH1 ((DMA_ChannelType *)0x40020008)
#define NS_DMA1_CH2 ((DMA_ChannelType *)0x4002001c)
#define NS_DMA1_CH3 ((DMA_ChannelType *)0x40020030)
#define NS_DMA1_CH4 ((DMA_ChannelType *)0x40020044)
#define NS_DMA1_CH5 ((DMA_ChannelType *)0x40020058)
#define NS_DMA1_CH6 ((DMA_ChannelType *)0x4002006c)
#define NS_DMA1_CH7 ((DMA_ChannelType *)0x40020080)
#define NS_DMA1_CH8 ((DMA_ChannelType *)0x40020094)

#define DMA_INT_TXC     ((uint32_t)0x00000002)

#define DMA1_INT_TXC1   ((uint32_t)0x00000002)
#define DMA1_INT_TXC4   ((uint32_t)0x00002000)
#define DMA1_INT_TXC5   ((uint32_t)0x00020000)
#define DMA1_FLAG_TXC1  ((uint32_t)0x00000002)
#define DMA1_FLAG_TXC4  ((uint32_t)0x00002000)
#define DMA1_FLAG_TXC5  ((uint32_t)0x00020000)

void DMA_DeInit(DMA_ChannelType *channel);
void DMA_Init(DMA_ChannelType *channel, DMA_InitType *DMA_InitParam);
void DMA_EnableChannel(DMA_ChannelType *channel);
void DMA_DisableChannel(DMA_ChannelType *channel);
void DMA_ConfigInt(DMA_ChannelType *channel, uint32_t DMA_INT);
uint32_t DMA_GetIntStatus(DMA_Module *DMAy, uint32_t DMAy_INT);
void DMA_ClrIntPendingBit(DMA_Module *DMAy, uint32_t DMAy_INT);
uint32_t DMA_GetFlagStatus(DMA_Module *DMAy, uint32_t DMAy_FLAG);
void DMA_ClearFlag(DMA_Module *DMAy, uint32_t DMAy_FLAG);
void DMA_RequestRemap(DMA_ChannelType *channel, uint32_t remap);

// Timer register layout used by the Nations peripheral library.  CTRL1,
// CTRL2, STS, and CCEN are 32-bit; the remaining registers used here are
// accessed as halfwords in the stock image.
typedef struct
{
    __IO uint32_t CR1;
    __IO uint32_t CR2;
    __IO uint16_t SMCR;
    uint16_t RESERVED0;
    __IO uint16_t DIER;
    uint16_t RESERVED1;
    __IO uint32_t SR;
    __IO uint16_t EGR;
    uint16_t RESERVED2;
    __IO uint16_t CCMR1;
    uint16_t RESERVED3;
    __IO uint16_t CCMR2;
    uint16_t RESERVED4;
    __IO uint32_t CCER;
    __IO uint16_t CNT;
    uint16_t RESERVED5;
    __IO uint16_t PSC;
    uint16_t RESERVED6;
    __IO uint16_t ARR;
    uint16_t RESERVED7;
    __IO uint16_t RCR;
    uint16_t RESERVED8;
    __IO uint16_t CCR1;
    uint16_t RESERVED9;
    __IO uint16_t CCR2;
    uint16_t RESERVED10;
    __IO uint16_t CCR3;
    uint16_t RESERVED11;
    __IO uint16_t CCR4;
    uint16_t RESERVED12;
    __IO uint16_t BDTR;
    uint16_t RESERVED13;
    __IO uint16_t DCTRL;
    uint16_t RESERVED14;
    __IO uint16_t DADDR;
    uint16_t RESERVED15;
} TIM_Module;

#define NS_TIM2 ((TIM_Module *)0x40000000)
#define NS_TIM3 ((TIM_Module *)0x40000400)
#define NS_TIM4 ((TIM_Module *)0x40000800)
#define NS_TIM5 ((TIM_Module *)0x40000c00)
#define NS_TIM6 ((TIM_Module *)0x40001000)
#define NS_TIM7 ((TIM_Module *)0x40001400)
#define NS_TIM1 ((TIM_Module *)0x40012c00)
#define NS_TIM8 ((TIM_Module *)0x40013400)

typedef struct
{
    uint16_t Prescaler;
    uint16_t CntMode;
    uint16_t Period;
    uint16_t ClkDiv;
    uint8_t RepetCnt;
    // The selectors are bool, not uint8_t: same size, but a bool load is
    // not a character access, so GCC may move it across the volatile
    // register stores in TIM_InitTimeBase, which is what stock's code does.
    bool CapCh1FromCompEn;
    bool CapCh2FromCompEn;
    bool CapCh3FromCompEn;
    bool CapCh4FromCompEn;
    bool CapEtrClrFromCompEn;
    bool CapEtrSelFromTscEn;
} TIM_TimeBaseInitType;

void TIM_InitTimeBase(TIM_Module *TIMx,
                      TIM_TimeBaseInitType *TIM_TimeBaseInitStruct);
void TIM_InitTimBaseStruct(TIM_TimeBaseInitType *TIM_TimeBaseInitStruct);
void TIM_TimeBaseInit(TIM_Module *TIMx, uint16_t period, uint16_t prescaler);
void TIM_SetEventGeneration(TIM_Module *TIMx, uint16_t value);
void TIM_ETRClockMode2Config(TIM_Module *TIMx, uint16_t prescaler,
                             uint16_t polarity, uint16_t filter);
void TIM_DMACmd(TIM_Module *TIMx, uint16_t request);
void TIM_Cmd(TIM_Module *TIMx);

// ----------------------------------------------------------------- RCC ----

typedef struct
{
    uint32_t SysclkFreq;        // 0x00
    uint32_t HclkFreq;          // 0x04
    uint32_t Pclk1Freq;         // 0x08
    uint32_t Pclk2Freq;         // 0x0c
    uint32_t AdcPllClkFreq;     // 0x10
    uint32_t AdcHclkFreq;       // 0x14
} RCC_ClocksType;

#define RCC_AHB_PERIPH_DMA1     ((uint32_t)0x00000001)
#define RCC_AHB_PERIPH_DMA2     ((uint32_t)0x00000002)
#define RCC_AHB_PERIPH_GPIOA    ((uint32_t)0x00000080)

#define RCC_APB2_PERIPH_AFIO    ((uint32_t)0x00000001)
#define RCC_APB2_PERIPH_USART1  ((uint32_t)0x00004000)

void RCC_EnableAHBPeriphClk(uint32_t RCC_AHBPeriph);
void RCC_EnableAPB2PeriphClk(uint32_t RCC_APB2Periph);
void RCC_GetClocksFreqValue(RCC_ClocksType *RCC_Clocks);

// ---------------------------------------------------------------- NVIC ----

typedef struct
{
    uint8_t NVIC_IRQChannel;                    // 0x00
    uint8_t NVIC_IRQChannelPreemptionPriority;  // 0x01
    uint8_t NVIC_IRQChannelSubPriority;         // 0x02
    uint8_t NVIC_IRQChannelCmd;                 // 0x03
} NVIC_InitType;

#define NVIC_PriorityGroup_0    ((uint32_t)0x700)

void NVIC_PriorityGroupConfig(uint32_t NVIC_PriorityGroup);
void NVIC_Init(NVIC_InitType *NVIC_InitStruct);

// N32G45x interrupt numbers.  Note these are NOT identical to a real
// STM32F103: USART1 is IRQ 36 here, where an F103 would have 37.
#define N32_DMA1_Channel1_IRQn  11
#define N32_DMA1_Channel4_IRQn  14
#define N32_DMA1_Channel5_IRQn  15
#define N32_USART1_IRQn         36

#endif // n32g45x.h
