// Nations N32G45x standard peripheral library - TIM driver.
// Only the subset used by the FlashForge levelBoard firmware is kept.

#include <stdint.h>
#include "n32g45x.h"


void
TIM_SetEventGeneration(TIM_Module *TIMx, uint16_t value)
{
    TIMx->EGR = value;
}

void
TIM_InitTimeBase(TIM_Module *TIMx, TIM_TimeBaseInitType *s)
{
    // TIM6 is a basic timer: it has no counter-mode, clock-division or
    // capture-input fields, so it takes the short path below.  Every other
    // instance gets the common counter fields plus whichever capture-input
    // selectors that particular timer supports.
    if (TIMx != NS_TIM6) {
        uint32_t tmp = TIMx->CR1;
        tmp &= ~NS_TIM_CR1_DIR_CMS;
        tmp |= s->CntMode;
        TIMx->CR1 = tmp;

        tmp = TIMx->CR1;
        tmp &= ~NS_TIM_CR1_CKD;
        TIMx->CR1 = tmp;
        TIMx->CR1 |= s->ClkDiv;

        TIMx->ARR = s->Period;
        TIMx->PSC = s->Prescaler;
        // Only the advanced timers have a repetition counter.  The hint
        // keeps TIM8 on the same fast path as TIM1: without it gcc treats
        // the second comparison as the unlikely one and reorders the tail.
        if (TIMx == NS_TIM1 || __builtin_expect(TIMx == NS_TIM8, 1))
            TIMx->RCR = s->RepetCnt;
        TIMx->EGR = NS_TIM_EGR_UG;

        if (s->CapCh1FromCompEn)
            TIMx->CR1 |= NS_TIM_CR1_CAP_CH1_FROM_CMP;
        else
            TIMx->CR1 &= ~NS_TIM_CR1_CAP_CH1_FROM_CMP;

        if (TIMx != NS_TIM1 && TIMx != NS_TIM8 && TIMx != NS_TIM2
            && TIMx != NS_TIM3 && TIMx != NS_TIM4)
            return;
        if (s->CapEtrClrFromCompEn)
            TIMx->CR1 |= NS_TIM_CR1_CAP_ETR_CLR_FROM_CMP;
        else
            TIMx->CR1 &= ~NS_TIM_CR1_CAP_ETR_CLR_FROM_CMP;

        if (TIMx != NS_TIM2)
            return;
        if (s->CapCh2FromCompEn)
            TIMx->CR1 |= NS_TIM_CR1_CAP_CH2_FROM_CMP;
        else
            TIMx->CR1 &= ~NS_TIM_CR1_CAP_CH2_FROM_CMP;
        if (s->CapCh3FromCompEn)
            TIMx->CR1 |= NS_TIM_CR1_CAP_CH3_FROM_CMP;
        else
            TIMx->CR1 &= ~NS_TIM_CR1_CAP_CH3_FROM_CMP;
        if (s->CapCh4FromCompEn)
            TIMx->CR1 |= NS_TIM_CR1_CAP_CH4_FROM_CMP;
        else
            TIMx->CR1 &= ~NS_TIM_CR1_CAP_CH4_FROM_CMP;
    } else {
        TIMx->ARR = s->Period;
        TIMx->PSC = s->Prescaler;
        TIMx->EGR = NS_TIM_EGR_UG;
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
    TIMx->CR1 |= NS_TIM_CR1_CEN;
}

void
TIM_ETRClockMode2Config(TIM_Module *TIMx, uint16_t prescaler,
                        uint16_t polarity, uint16_t filter)
{
    uint16_t psc = prescaler;
    uint16_t tmp = TIMx->SMCR;
    tmp &= (uint16_t)~NS_TIM_SMCR_ETF;
    tmp |= (uint16_t)(filter << 8);
    TIMx->SMCR = tmp;
    if (polarity == NS_TIM_SMCR_ETP)
        TIMx->SMCR |= NS_TIM_SMCR_ETP;
    else
        TIMx->SMCR &= (uint16_t)~NS_TIM_SMCR_ETP;
    tmp = TIMx->SMCR;
    tmp &= (uint16_t)~NS_TIM_SMCR_ETPS;
    tmp |= psc;
    TIMx->SMCR = tmp;
    TIMx->SMCR = (uint16_t)(TIMx->SMCR | NS_TIM_SMCR_ECE);
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
