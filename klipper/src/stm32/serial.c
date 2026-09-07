// STM32 serial
//
// Copyright (C) 2019  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h" // CONFIG_SERIAL_BAUD
#include "board/armcm_boot.h" // armcm_enable_irq
#include "board/serial_irq.h" // serial_rx_byte
#include "command.h" // DECL_CONSTANT_STR
#include "internal.h" // enable_pclock
#include "sched.h" // DECL_INIT

#if CONFIG_MACH_N32G45x && CONFIG_STM32_SERIAL_USART1
// ==========================================================================
// FlashForge "levelBoard" (Nations N32G45x) reconstruction.
//
// The stock console is upstream Klipper's byte-at-a-time USART1 RXNE/TXE
// interrupt path, not DMA driven, accessed through the Nations N32G45x
// peripheral library (lib/n32g45x) instead of Klipper's generic
// enable_pclock()/gpio_peripheral()/armcm_enable_irq() stm32 helpers, and
// with USART registers accessed 16 bits wide.  See
// tools/mcu-recovery/recovered_serial.md for the full analysis, addresses
// and per-function verification against the stock image.
// ==========================================================================
#include "n32g45x.h" // NS_USART1

DECL_CONSTANT_STR("RESERVE_PINS_serial", "PH10,PH9");

#define CR1_FLAGS (USART_CTRL1_UEN | USART_CTRL1_REN | USART_CTRL1_TEN \
                   | USART_CTRL1_RXDNEIEN)

void
USARTx_IRQHandler(void)
{
    uint16_t sr = NS_USART1->STS;
    if (sr & (USART_STS_RXDNE | USART_STS_OREF)) {
        // The ORE flag is automatically cleared by reading SR, followed
        // by reading DR.
        serial_rx_byte(NS_USART1->DAT);
    }
    if (sr & USART_STS_TXDE && NS_USART1->CTRL1 & USART_CTRL1_TXDEIEN) {
        uint8_t data;
        int ret = serial_get_tx_byte(&data);
        if (ret)
            NS_USART1->CTRL1 = CR1_FLAGS;
        else
            NS_USART1->DAT = data;
    }
}
DECL_ARMCM_IRQ(USARTx_IRQHandler, N32_USART1_IRQn);

void
serial_enable_tx_irq(void)
{
    NS_USART1->CTRL1 = CR1_FLAGS | USART_CTRL1_TXDEIEN;
}

// Vestigial DMA transmit path.  The stock firmware still carries these two
// handlers (and still turns on the DMA1 clock in serial_init), but nothing
// ever configures or starts DMA1 channel 4/5 for USART1, so neither handler
// can run and this flag is only ever cleared.
uint8_t tx_dma_active;

void
DMA1_Channel4_IRQHandler(void)
{
    if (DMA_GetFlagStatus(NS_DMA1, DMA1_FLAG_TXC4)) {
        DMA_ClearFlag(NS_DMA1, DMA1_FLAG_TXC4);
        USART_ClrFlag(NS_USART1, USART_FLAG_TXC);
        DMA_DisableChannel(NS_DMA1_CH4);
        tx_dma_active = 0;
    }
}
DECL_ARMCM_IRQ(DMA1_Channel4_IRQHandler, N32_DMA1_Channel4_IRQn);

void
DMA1_Channel5_IRQHandler(void)
{
    if (DMA_GetIntStatus(NS_DMA1, DMA1_INT_TXC5))
        DMA_ClrIntPendingBit(NS_DMA1, DMA1_INT_TXC5);
}
DECL_ARMCM_IRQ(DMA1_Channel5_IRQHandler, N32_DMA1_Channel5_IRQn);

// Stock's vector table is 69 words long: IRQ 0..52.  IRQ 52 (UART4 on this
// part's numbering) is padded out to a DefaultHandler slot even though
// UART4's base address, 0x40004C00, appears nowhere in the image -- UART4
// is not used.  What actually causes the table to extend that far is not
// known (no peripheral in this range is otherwise touched); this
// declaration reproduces the table's length and bytes without asserting a
// mechanism for it.
DECL_ARMCM_IRQ(DefaultHandler, 52);

void
serial_init(void)
{
    GPIO_InitType gpio;
    NVIC_InitType nvic;
    USART_InitType usart;

    RCC_EnableAHBPeriphClk(RCC_AHB_PERIPH_DMA1);
    RCC_EnableAHBPeriphClk(RCC_AHB_PERIPH_GPIOA);
    RCC_EnableAPB2PeriphClk(RCC_APB2_PERIPH_AFIO);
    RCC_EnableAPB2PeriphClk(RCC_APB2_PERIPH_USART1);

    GPIO_InitStruct(&gpio);
    gpio.Pin = GPIO_PIN_9;
    gpio.GPIO_Mode = GPIO_MODE_AF_PP;
    gpio.GPIO_Pull = GPIO_PULL_UP;
    gpio.GPIO_Alternate = GPIO_AF5_USART1;
    GPIO_InitPeripheral(NS_GPIOA, &gpio);
    gpio.Pin = GPIO_PIN_10;
    gpio.GPIO_Alternate = GPIO_AF5_USART1;
    GPIO_InitPeripheral(NS_GPIOA, &gpio);

    nvic.NVIC_IRQChannel = N32_USART1_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;
    nvic.NVIC_IRQChannelSubPriority = 3;
    nvic.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&nvic);

    USART_StructInit(&usart);
    usart.BaudRate = CONFIG_SERIAL_BAUD;
    usart.WordLength = USART_WL_8B;
    usart.StopBits = USART_STPB_1;
    usart.Parity = USART_PE_NO;
    usart.Mode = USART_MODE_RX | USART_MODE_TX;
    usart.HardwareFlowControl = USART_HFCTRL_NONE;
    USART_Init(NS_USART1, &usart);

    USART_ConfigInt(NS_USART1, USART_INT_RXDNE);
    USART_Enable(NS_USART1);
}
DECL_INIT(serial_init);

#else // !(CONFIG_MACH_N32G45x && CONFIG_STM32_SERIAL_USART1)

// Select the configured serial port
#if CONFIG_STM32_SERIAL_USART1
  DECL_CONSTANT_STR("RESERVE_PINS_serial", "PH10,PH9");
  #define GPIO_Rx GPIO('A', 10)
  #define GPIO_Tx GPIO('A', 9)
  #define USARTx USART1
  // Stock installs this handler on vector 36 and unmasks NVIC line 36.
  // The Nations CMSIS header numbers this part exactly like an F103 --
  // a contiguous enum in which 36 is SPI2 and USART1 is 37 -- so on the
  // published numbering this handler sits on the wrong vector and can
  // never fire.  Neither the SPI2 nor the UART4 base address appears
  // anywhere in the image.  Reproducing the image requires 36; whether
  // the shipped silicon really numbers USART1 at 36 is unresolved.
  #define USARTx_IRQn SPI2_IRQn
#elif CONFIG_STM32_SERIAL_USART1_ALT_PB7_PB6
  DECL_CONSTANT_STR("RESERVE_PINS_serial", "PB7,PB6");
  #define GPIO_Rx GPIO('B', 7)
  #define GPIO_Tx GPIO('B', 6)
  #define USARTx USART1
  #define USARTx_IRQn USART1_IRQn
#elif CONFIG_STM32_SERIAL_USART2
  DECL_CONSTANT_STR("RESERVE_PINS_serial", "PA3,PA2");
  #define GPIO_Rx GPIO('A', 3)
  #define GPIO_Tx GPIO('A', 2)
  #define USARTx USART2
  #define USARTx_IRQn USART2_IRQn
#elif CONFIG_STM32_SERIAL_USART2_ALT_PD6_PD5
  DECL_CONSTANT_STR("RESERVE_PINS_serial", "PD6,PD5");
  #define GPIO_Rx GPIO('D', 6)
  #define GPIO_Tx GPIO('D', 5)
  #define USARTx USART2
  #define USARTx_IRQn USART2_IRQn
#elif CONFIG_STM32_SERIAL_USART3
  DECL_CONSTANT_STR("RESERVE_PINS_serial", "PB11,PB10");
  #define GPIO_Rx GPIO('B', 11)
  #define GPIO_Tx GPIO('B', 10)
  #define USARTx USART3
  #define USARTx_IRQn USART3_IRQn
#elif CONFIG_STM32_SERIAL_USART3_ALT_PD9_PD8
  DECL_CONSTANT_STR("RESERVE_PINS_serial", "PD9,PD8");
  #define GPIO_Rx GPIO('D', 9)
  #define GPIO_Tx GPIO('D', 8)
  #define USARTx USART3
  #define USARTx_IRQn USART3_IRQn
#endif

#define CR1_FLAGS (USART_CR1_UE | USART_CR1_RE | USART_CR1_TE   \
                   | USART_CR1_RXNEIE)

void
USARTx_IRQHandler(void)
{
    uint32_t sr = USARTx->SR;
    if (sr & (USART_SR_RXNE | USART_SR_ORE)) {
        // The ORE flag is automatically cleared by reading SR, followed
        // by reading DR.
        serial_rx_byte(USARTx->DR);
    }
    if (sr & USART_SR_TXE && USARTx->CR1 & USART_CR1_TXEIE) {
        uint8_t data;
        int ret = serial_get_tx_byte(&data);
        if (ret)
            USARTx->CR1 = CR1_FLAGS;
        else
            USARTx->DR = data;
    }
}

void
serial_enable_tx_irq(void)
{
    USARTx->CR1 = CR1_FLAGS | USART_CR1_TXEIE;
}

void
serial_init(void)
{
    enable_pclock((uint32_t)USARTx);

    uint32_t pclk = get_pclock_frequency((uint32_t)USARTx);
    uint32_t div = DIV_ROUND_CLOSEST(pclk, CONFIG_SERIAL_BAUD);
    USARTx->BRR = (((div / 16) << USART_BRR_DIV_Mantissa_Pos)
                   | ((div % 16) << USART_BRR_DIV_Fraction_Pos));
    USARTx->CR1 = CR1_FLAGS;
    armcm_enable_irq(USARTx_IRQHandler, USARTx_IRQn, 0);

    gpio_peripheral(GPIO_Rx, GPIO_FUNCTION(7), 1);
    gpio_peripheral(GPIO_Tx, GPIO_FUNCTION(7), 0);
}
DECL_INIT(serial_init);

#endif // CONFIG_MACH_N32G45x && CONFIG_STM32_SERIAL_USART1
