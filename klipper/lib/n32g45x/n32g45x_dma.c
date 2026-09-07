// Nations N32G45x standard peripheral library - DMA driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"


void
DMA_DeInit(DMA_ChannelType *channel)
{
    channel->CHCFG &= ~DMA_CHCFG_CHEN;
    channel->CHCFG = 0;
    channel->TXNUM = 0;
    channel->PADDR = 0;
    channel->MADDR = 0;
    if (channel == NS_DMA1_CH1)
        NS_DMA1->INTCLR |= DMA1_CH1_INT_MASK;
    else if (channel == NS_DMA1_CH2)
        NS_DMA1->INTCLR |= DMA1_CH2_INT_MASK;
    else if (channel == NS_DMA1_CH3)
        NS_DMA1->INTCLR |= DMA1_CH3_INT_MASK;
    else if (channel == NS_DMA1_CH4)
        NS_DMA1->INTCLR |= DMA1_CH4_INT_MASK;
    else if (channel == NS_DMA1_CH5)
        NS_DMA1->INTCLR |= DMA1_CH5_INT_MASK;
    else if (channel == NS_DMA1_CH6)
        NS_DMA1->INTCLR |= DMA1_CH6_INT_MASK;
    else if (channel == NS_DMA1_CH7)
        NS_DMA1->INTCLR |= DMA1_CH7_INT_MASK;
    else if (channel == NS_DMA1_CH8)
        NS_DMA1->INTCLR |= DMA1_CH8_INT_MASK;
}

void
DMA_Init(DMA_ChannelType *channel, DMA_InitType *DMA_InitParam)
{
    channel->PADDR = DMA_InitParam->PeriphAddr;
    channel->MADDR = DMA_InitParam->MemAddr;

    // Each configuration field is cleared and then set on its own, so a
    // channel can be reconfigured field by field without disturbing the
    // rest of the control register.
    int dir = DMA_InitParam->Direction;
    channel->CHCFG &= ~DMA_CHCFG_DIR_MASK;
    channel->CHCFG |= dir;
    int bufsize = DMA_InitParam->BufSize;
    channel->TXNUM = bufsize;
    int pinc = DMA_InitParam->PeriphInc;
    channel->CHCFG &= ~DMA_CHCFG_PERIPH_INC_MASK;
    channel->CHCFG |= pinc;
    int minc = DMA_InitParam->DMA_MemoryInc;
    channel->CHCFG &= ~DMA_CHCFG_MEM_INC_MASK;
    channel->CHCFG |= minc;
    int psize = DMA_InitParam->PeriphDataSize;
    channel->CHCFG &= ~DMA_CHCFG_PERIPH_DATA_SIZE_MASK;
    channel->CHCFG |= psize;
    int msize = DMA_InitParam->MemDataSize;
    channel->CHCFG &= ~DMA_CHCFG_MEM_DATA_SIZE_MASK;
    channel->CHCFG |= msize;
    int circ = DMA_InitParam->CircularMode;
    channel->CHCFG &= ~DMA_CHCFG_CIRC_MASK;
    channel->CHCFG |= circ;
    int prio = DMA_InitParam->Priority;
    channel->CHCFG &= ~DMA_CHCFG_PRIORITY_MASK;
    channel->CHCFG |= prio;
    int m2m = DMA_InitParam->Mem2Mem;
    channel->CHCFG &= ~DMA_CHCFG_M2M_MASK;
    channel->CHCFG |= m2m;
}

void
DMA_EnableChannel(DMA_ChannelType *channel)
{
    channel->CHCFG |= DMA_CHCFG_CHEN;
}

void
DMA_DisableChannel(DMA_ChannelType *channel)
{
    channel->CHCFG &= ~DMA_CHCFG_CHEN;
}

void
DMA_ConfigInt(DMA_ChannelType *channel, uint32_t DMA_INT)
{
    channel->CHCFG |= DMA_INT;
}

// DMA_GetIntStatus and DMA_GetFlagStatus are the same test twice; the SDK
// declares both, so both are kept.  Channel 5 uses the interrupt pair,
// channels 1 and 4 the flag pair.
uint32_t
DMA_GetIntStatus(DMA_Module *DMAy, uint32_t DMAy_INT)
{
    return (DMAy_INT & DMAy->INTSTS) ? 1 : 0;
}

void
DMA_ClrIntPendingBit(DMA_Module *DMAy, uint32_t DMAy_INT)
{
    DMAy->INTCLR = DMAy_INT;
}

uint32_t
DMA_GetFlagStatus(DMA_Module *DMAy, uint32_t DMAy_FLAG)
{
    return (DMAy->INTSTS & DMAy_FLAG) ? 1 : 0;
}

void
DMA_ClearFlag(DMA_Module *DMAy, uint32_t DMAy_FLAG)
{
    DMAy->INTCLR = DMAy_FLAG;
}

void
DMA_RequestRemap(DMA_ChannelType *channel, uint32_t remap)
{
    channel->CHSEL = remap;
}
