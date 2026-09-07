// Nations N32G45x standard peripheral library - DMA driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"


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

void
DMA_Init(DMA_ChannelType *channel, DMA_InitType *DMA_InitParam)
{
    channel->PADDR = DMA_InitParam->PeriphAddr;
    channel->MADDR = DMA_InitParam->MemAddr;

    // Each configuration field is cleared and then set on its own, so a
    // channel can be reconfigured field by field without disturbing the
    // rest of the control register.
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

void
DMA_EnableChannel(DMA_ChannelType *channel)
{
    channel->CHCFG |= (uint32_t)0x0001;
}

void
DMA_DisableChannel(DMA_ChannelType *channel)
{
    channel->CHCFG &= ~((uint32_t)0x0001);
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
