// Nations N32G45x standard peripheral library - TIM driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"


void
TIM_SetEventGeneration(TIM_Module *TIMx, uint16_t value)
{
    TIMx->EGR = value;
}

__attribute__((noipa)) void
TIM_InitTimeBase(TIM_Module *TIMx, TIM_TimeBaseInitType *s)
{
    // TIM6 is a basic timer: it has no counter-mode, clock-division or
    // capture-input fields, so it takes the short path below.  Every other
    // instance gets the common counter fields plus whichever capture-input
    // selectors that particular timer supports.
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
        // Only the advanced timers have a repetition counter.  TIM8 is as
        // likely as TIM1 at the call sites here, so say so rather than let
        // the compiler assume the equality usually fails.
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

__attribute__((noipa)) void
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

void
TIM_Cmd(TIM_Module *TIMx)
{
    // The levelBoard only ever starts a timer, never stops one, so this
    // helper drops the SDK's enable/disable argument.
    TIMx->CR1 |= 1;
}

void
TIM_ETRClockMode2Config(TIM_Module *TIMx, uint16_t prescaler,
                        uint16_t polarity, uint16_t filter)
{
    uint16_t psc = prescaler;
    uint16_t tmp = TIMx->SMCR;
    tmp &= (uint16_t)~0x0f00;
    tmp |= (uint16_t)(filter << 8);
    TIMx->SMCR = tmp;
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

void
TIM_DMACmd(TIM_Module *TIMx, uint16_t request)
{
    TIMx->DIER = (uint16_t)(TIMx->DIER | request);
}

static TIM_TimeBaseInitType TIM_TimeBaseInitStructure;

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
