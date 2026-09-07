// Creator 5 levelBoard -- eddy current bed probe front end.
//
// The probe is an LC oscillator whose frequency is pulled by the steel
// bed; there is no ADC anywhere in this module.  The oscillator output
// drives PA0 as TIM8_ETR, and TIM8 runs in external clock mode 2 with
// ARR=500, so it raises an update event once every 501 oscillator
// edges.  TIM1 free-runs off the internal timer clock as a plain 16-bit
// tick counter (PSC=0, ARR=0xffff).  DMA1 channel 1 is armed circular,
// one halfword, TIM1->CNT into a single RAM word, requested by the TIM8
// update.  Every DMA completion interrupt therefore hands us the TIM1
// count at that moment, and the difference between successive captures
// is
//
//     ticks elapsed while the oscillator produced 501 edges
//
// i.e. a reciprocal frequency (period) measurement, 16 bits wide.  That
// difference is the "value" the host sees.  A larger value means a
// lower oscillator frequency, which means metal closer.  At 128 MHz one
// tick is 7.8125 ns.
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <stdint.h> // uint32_t
#include "autoconf.h" // CONFIG_CLOCK_FREQ
#include "board/armcm_boot.h" // DECL_ARMCM_IRQ
#include "board/internal.h" // TIM1
#include "board/irq.h" // irq_disable
#include "board/misc.h" // timer_read_time
#include "ff_flashforge.h" // ff_eddy_value
#include "n32g45x.h" // NVIC_Init
#include "sched.h" // sched_wake_task

// External oscillator edges per captured sample: TIM8 raises its update
// event every ARR+1 = 501 edges.
#define FF_EDDY_GATE_ARR 500

// One sample is consumed per polling timer tick.
#define FF_EDDY_SAMPLE_US 500

// Ring buffer for the noise statistics.  Odd, so the median is an
// element rather than an average.
#define FF_EDDY_NSAMP 11

// Deviation, in TIM1 ticks, above which a sample is a gross excursion
// rather than noise.
#define FF_EDDY_HARD_DEV 150

// Consecutive gross excursions before the endstop is forced to trigger.
#define FF_EDDY_HARD_COUNT 15

// Consecutive out-of-threshold samples before the sampling reference is
// dragged to the current reading.
#define FF_EDDY_DRIFT_COUNT 100

// The auto-calibrated threshold is 3*sigma clamped to this range.
#define FF_EDDY_THRESH_MIN 20
#define FF_EDDY_THRESH_MAX 60

// The signal must stay this quiet before a recalibration is accepted.
#define FF_EDDY_QUIET_MS 2000

// Debounce depths: the 4th consecutive sample past the threshold trips
// the endstop, the 3rd consecutive sample below it releases.
#define FF_EDDY_TRIG_COUNT   4
#define FF_EDDY_UNTRIG_COUNT 3

// Hysteresis, in ticks, below the trigger threshold.
#define FF_EDDY_HYSTERESIS 2

// Smallest sample that can be a real period measurement.
#define FF_EDDY_VALUE_MIN 2


/****************************************************************
 * State
 ****************************************************************/

// Virtual endstop pin level.  1 == not triggered, 0 == triggered.
// gpio_in_read() returns this instead of a port bit for the probe pin.
volatile bool ff_eddy_pin_state = true;

// Threshold the detector actually compares against.  The host can set
// it, but ff_eddy_update() overwrites it on every recalibration, so a
// host-supplied value only lasts until the bed goes quiet.
int16_t ff_eddy_threshold = 25;

// Largest median absolute deviation still considered "quiet".
uint32_t ff_eddy_mad_limit = 2;

struct timer ff_eddy_timer;
struct task_wake ff_eddy_wake;
// Set once the first calibration has finished; never cleared.
uint8_t ff_eddy_armed;

static uint32_t ff_eddy_prev_cnt;
static volatile uint32_t ff_eddy_dma_capture;
// Latest absolute deviation, fed straight back into the trigger filter.
static volatile uint32_t ff_eddy_last_dev;
// Baseline as it stood when the sensor first armed.  Reported over the
// debug probe; nothing in the firmware reads it back.
uint32_t ff_eddy_dbg_baseline;
static uint8_t ff_eddy_have_filter;
static volatile uint8_t ff_eddy_hard_trigger;
static volatile uint32_t ff_eddy_mad;
uint32_t ff_eddy_baseline;
static int32_t ff_eddy_trig_acc;
static uint32_t ff_eddy_filter_acc;
uint32_t ff_eddy_sample_ref;
static volatile uint32_t ff_eddy_sample;
volatile uint32_t ff_eddy_value;
static volatile uint32_t ff_eddy_sample_ready;
uint8_t ff_eddy_calibrated;
static uint16_t ff_eddy_outrange_count;
static uint32_t ff_eddy_ring[FF_EDDY_NSAMP];
static uint8_t ff_eddy_ring_count;
static uint8_t ff_eddy_ring_pos;
static uint16_t ff_eddy_inrange_count;
static uint32_t ff_eddy_quiet_start_ms;
static uint8_t ff_eddy_untrig_count;
// Constant offset added when re-baselining, for a probe that reads
// consistently high or low.  Left at zero on this board.
uint32_t ff_eddy_offset;
static volatile uint8_t ff_eddy_trig_count;
volatile int32_t ff_eddy_peel;




/****************************************************************
 * Small helpers
 ****************************************************************/

// The cycle counter runs at the core clock, so this is an exact
// divide by 128000 on this board.
static uint32_t
ff_eddy_now_ms(void)
{
    return timer_read_time() / (CONFIG_CLOCK_FREQ / 1000);
}

// Copy the ring, sort the copy, return the middle element.
static uint32_t noinline __section(".text.eddy_median")
ff_eddy_median(void)
{
    uint32_t tmp[FF_EDDY_NSAMP];
    int32_t i, j;
    for (i = 0; i < FF_EDDY_NSAMP; i++)
        tmp[i] = ff_eddy_ring[i];
    for (i = 1; i < FF_EDDY_NSAMP; i++) {
        uint32_t key = tmp[i];
        j = i - 1;
        while (j >= 0 && tmp[j] > key) {
            tmp[j + 1] = tmp[j];
            j--;
        }
        tmp[j + 1] = key;
    }
    return tmp[FF_EDDY_NSAMP / 2];
}

// Drop the detector back to the untriggered state before a homing move
// starts.  Called from command_endstop_home and endstop_recover_state.
//
// NOT FLASHFORGE'S SOURCE.  This body is hand-written assembly standing
// in for six C assignments, because the compiler schedules the C form
// differently.  See mcu/levelBoard/notes/realism-audit.md, entry A9.
void __attribute__((naked, used))
ff_eddy_home_reset(void)
{
    __asm__ volatile(
        "push {r4}\n"
        "ldr r2, =ff_eddy_pin_state\n"
        "ldr r4, =ff_eddy_trig_acc\n"
        "ldr r0, =ff_eddy_trig_count\n"
        "ldr r1, =ff_eddy_untrig_count\n"
        "movs r3, #0\n"
        "mov.w ip, #1\n"
        "strb.w ip, [r2]\n"
        "str r3, [r4]\n"
        "ldr r2, =ff_eddy_peel\n"
        "ldr r4, =ff_eddy_hard_trigger\n"
        "strb r3, [r0]\n"
        "strb r3, [r1]\n"
        "strb r3, [r4]\n"
        "ldr.w r4, [sp], #4\n"
        "str r3, [r2]\n"
        "bx lr\n"
    );
}

// Integer square root, Newton's method.
static uint32_t
ff_eddy_isqrt(uint32_t v)
{
    if (unlikely(!v))
        return 0;
    uint32_t r = v;
    uint32_t next = (v + 1) >> 1;
    while (next < r) {
        r = next;
        next = (v / r + r) >> 1;
    }
    return r;
}


/****************************************************************
 * Front end: TIM8 gate, TIM1 tick counter, DMA1 channel 1
 ****************************************************************/

// DMA1 channel 1: TIM1->CNT into one RAM word, circular, requested by
// the TIM8 update event.  DMA_DeInit() first, which also clears our
// bits in DMA1->IFCR.
void
ff_eddy_dma_init(void)
{
    DMA_InitType dma;
    RCC_EnableAHBPeriphClk(RCC_AHB_PERIPH_DMA1);
    DMA_DeInit(NS_DMA1_CH1);
    dma.PeriphAddr = (uint32_t)&TIM1->CNT;
    dma.MemAddr = (uint32_t)&ff_eddy_dma_capture;
    dma.Direction = 0;
    dma.BufSize = 1;
    dma.PeriphInc = 0;
    dma.DMA_MemoryInc = 0;
    dma.PeriphDataSize = 0x100;
    dma.MemDataSize = 0x400;
    dma.CircularMode = 0x20;
    dma.Priority = 0x2000;
    dma.Mem2Mem = 0;
    DMA_Init(NS_DMA1_CH1, &dma);
    DMA_RequestRemap(NS_DMA1_CH1, 0x32);

    NVIC_InitType nvic;
    nvic.NVIC_IRQChannel = N32_DMA1_Channel1_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;
    nvic.NVIC_IRQChannelSubPriority = 7;
    nvic.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&nvic);
    DMA_ConfigInt(NS_DMA1_CH1, DMA_INT_TXC);
    DMA_EnableChannel(NS_DMA1_CH1);
}

// Bring up the gate (TIM8 counting oscillator edges on PA0) and the
// tick counter (TIM1 free running), then arm the DMA.
void
ff_eddy_counter_init(void)
{
    RCC_EnableAPB2PeriphClk(0x2000);
    {
        GPIO_InitType gpio;
        GPIO_InitStruct(&gpio);
        gpio.Pin = 1;
        gpio.GPIO_Mode = GPIO_MODE_AF_PP;
        gpio.GPIO_Current = 2;      // 8mA drive
        gpio.GPIO_Alternate = 8;    // TIM8_ETR
        GPIO_InitPeripheral(NS_GPIOA, &gpio);
    }

    TIM_TimeBaseInit(NS_TIM8, FF_EDDY_GATE_ARR, 0);
    TIM_ETRClockMode2Config(NS_TIM8, 0, 0, 0);
    TIM_DMACmd(NS_TIM8, 0x100);
    TIM_Cmd(NS_TIM8);

    RCC_EnableAPB2PeriphClk(0x800);
    TIM_Module *tim1 = (TIM_Module *)((char *)NS_TIM8 - 0x800);
    TIM_TimeBaseInit(tim1, 0xffff, 0);
    TIM_SetEventGeneration(tim1, 1);
    TIM_Cmd(tim1);

    ff_eddy_dma_init();
}

// One capture per 501 oscillator edges.  The difference between
// successive TIM1 counts is the sample.
void
DMA1_Channel1_IRQHandler(void)
{
    if (!DMA_GetFlagStatus(NS_DMA1, DMA1_FLAG_TXC1))
        return;
    DMA_ClearFlag(NS_DMA1, DMA1_FLAG_TXC1);

    uint32_t cnt = ff_eddy_dma_capture;
    uint32_t delta = (uint16_t)(cnt - ff_eddy_prev_cnt);
    ff_eddy_prev_cnt = cnt;
    ff_eddy_sample = delta;
    ff_eddy_sample_ready = 1;
    ff_eddy_value = delta;
    sched_wake_task(&ff_eddy_wake);
}
DECL_ARMCM_IRQ(DMA1_Channel1_IRQHandler, 11);


/****************************************************************
 * Sample processing and auto calibration
 ****************************************************************/

// Called from the 500us polling timer, not from the DMA interrupt, so
// at most one sample is consumed per 500us however fast the oscillator
// runs.
void
ff_eddy_update(void)
{
    if (!ff_eddy_sample_ready)
        return;

    uint32_t store;                             // what goes into the ring
    if (!ff_eddy_armed) {
        // Not calibrated yet: the raw reading is the signal.
        ff_eddy_inrange_count = 0;
        ff_eddy_outrange_count = 0;
        store = ff_eddy_sample;
    } else {
        int32_t dev = ff_eddy_sample - ff_eddy_sample_ref;
        uint16_t adev = dev < 0 ? (uint16_t)-dev : (uint16_t)dev;
        int32_t thr = ff_eddy_threshold;
        uint16_t athr = thr < 0 ? -thr : thr;

        if (adev > athr && adev <= FF_EDDY_HARD_DEV) {
            // Beyond the threshold but not wildly so: this is what a
            // real probe touch looks like.  Feed the *baseline* to the
            // statistics so a trigger does not pollute the noise
            // estimate.
            store = ff_eddy_baseline;
            ff_eddy_inrange_count++;
            ff_eddy_outrange_count = 0;
            if (ff_eddy_inrange_count >= FF_EDDY_DRIFT_COUNT) {
                // Stuck off-baseline for 100 samples: assume drift and
                // move the reference.
                ff_eddy_inrange_count = 0;
                uint32_t v = ff_eddy_sample;
                ff_eddy_baseline = v;
                ff_eddy_sample_ref = v;
                store = ff_eddy_sample;
            }
        } else if (adev > FF_EDDY_HARD_DEV) {
            // Gross excursion.  Still fed raw, but after a run of them
            // the endstop is forced to trigger.
            store = ff_eddy_sample;
            if (++ff_eddy_outrange_count >= FF_EDDY_HARD_COUNT) {
                ff_eddy_hard_trigger = 1;
                ff_eddy_outrange_count = 0;
            }
        } else {
            // Quiet: feed the raw reading to the statistics.
            ff_eddy_inrange_count = 0;
            ff_eddy_outrange_count = 0;
            store = ff_eddy_sample;
        }
    }

    // --- common tail ---
    ff_eddy_sample_ready = 0;
    ff_eddy_ring[ff_eddy_ring_pos] = store;
    ff_eddy_ring_pos++;
    if (unlikely(ff_eddy_ring_pos > FF_EDDY_NSAMP - 1))
        ff_eddy_ring_pos = 0;
    if (ff_eddy_ring_count < FF_EDDY_NSAMP)
        ff_eddy_ring_count++;

    // Seed the smoothing filter once the ring is full.
    if (!ff_eddy_have_filter) {
        if (ff_eddy_ring_count == FF_EDDY_NSAMP) {
            ff_eddy_filter_acc = ff_eddy_median() * 4;
            ff_eddy_have_filter = 1;
            ff_eddy_quiet_start_ms = ff_eddy_now_ms();
        }
        return;
    }

    // Smoothing filter, held at 4x scale: acc = x + 3*acc/4, so
    // acc/4 is a first order low pass with alpha = 1/4.
    ff_eddy_filter_acc = store + (ff_eddy_filter_acc * 3) / 4;

    // Robust noise estimate: median absolute deviation about the
    // median of the ring.
    uint32_t center = ff_eddy_median();
    uint32_t devs[FF_EDDY_NSAMP];
    uint32_t i;
    for (i = 0; i < FF_EDDY_NSAMP; i++) {
        uint32_t s = ff_eddy_ring[i];
        devs[i] = s >= center ? s - center : center - s;
    }
    int32_t si, sj;
    for (si = 1; si < FF_EDDY_NSAMP; si++) {
        uint32_t key = devs[si];
        sj = si - 1;
        while (sj >= 0) {
            uint32_t cur = devs[sj];
            if (key >= cur)
                break;
            devs[sj + 1] = cur;
            sj--;
        }
        devs[sj + 1] = key;
    }
    uint32_t mad = devs[FF_EDDY_NSAMP / 2];
    // NOT FLASHFORGE'S SOURCE.  Placeholder for a statement we have not
    // recovered: both arms are deliberately identical so that it emits
    // nothing.  See mcu/levelBoard/notes/realism-audit.md, entry A4.
    if (ff_eddy_ring_pos)
        ff_eddy_mad = mad;
    else
        ff_eddy_mad = mad;

    if (ff_eddy_mad_limit < mad) {
        // Noisy: restart the quiet timer.
        ff_eddy_quiet_start_ms = 0;
        return;
    }
    uint32_t now = ff_eddy_now_ms();
    if (!ff_eddy_quiet_start_ms)
        ff_eddy_quiet_start_ms = now;
    if (now - ff_eddy_quiet_start_ms < FF_EDDY_QUIET_MS)
        return;

    // --- 2s of quiet: recalibrate ---
    uint64_t sumsq = 0;
    for (i = 0; i < FF_EDDY_NSAMP; i++) {
        int32_t d = ff_eddy_ring[i] - center;
        sumsq += (int32_t)(d * d);
    }
    uint32_t sd = ff_eddy_isqrt((uint32_t)(sumsq / FF_EDDY_NSAMP));

    // Never let sigma fall below 1.5 * MAD, and never below 1.
    int32_t mad3over2 = mad + mad / 2;
    uint32_t floor_sd = mad3over2;
    if (!floor_sd)
        floor_sd = 1;
    if (sd < floor_sd)
        sd = floor_sd;

    // Scrub outliers out of the ring.  This has no observable effect:
    // ring_count and ring_pos are reset a few lines below, so every slot
    // is overwritten before it is read again.
    if (ff_eddy_ring_count) {
        uint32_t lim;
        if (mad) {
            // Saturating 3*MAD.
            uint64_t t = (uint64_t)mad * 3;
            if (t > 0xffffffffull)
                lim = 0xffffffffu;
            else
                lim = mad * 3;
        } else {
            lim = ff_eddy_mad_limit;
        }
        for (i = 0; i < ff_eddy_ring_count; i++) {
            uint32_t s = ff_eddy_ring[i];
            uint32_t d = s >= center ? s - center : center - s;
            if (lim < d)
                ff_eddy_ring[i] = center;
        }
    }

    // The trigger threshold is derived from the noise, NOT from what
    // the host asked for: 3 sigma, truncated to int16, clamped 20..60.
    // Clamp min first, then max.
    int16_t thr = (int16_t)(sd * 3);
    if (thr < FF_EDDY_THRESH_MIN)
        thr = FF_EDDY_THRESH_MIN;
    if (thr >= FF_EDDY_THRESH_MAX)
        thr = FF_EDDY_THRESH_MAX;
    ff_eddy_threshold = thr;

    ff_eddy_baseline = ff_eddy_offset + ff_eddy_filter_acc / 4;
    ff_eddy_sample_ref = ff_eddy_baseline;
    ff_eddy_have_filter = 0;
    ff_eddy_calibrated = 1;
    ff_eddy_ring_count = 0;
    ff_eddy_ring_pos = 0;
    ff_eddy_quiet_start_ms = 0;
    ff_eddy_inrange_count = 0;
    ff_eddy_outrange_count = 0;
}

/****************************************************************
 * Host commands
 ****************************************************************/

// Re-zero everything against the current reading and declare the sensor
// calibrated.  Called by get_basic_param.
void
ff_eddy_rebaseline(void)
{
    irq_disable();
    uint32_t base = ff_eddy_value + ff_eddy_offset;
    ff_eddy_baseline = base;
    ff_eddy_sample_ref = base;
    ff_eddy_ring_count = 0;
    ff_eddy_ring_pos = 0;
    ff_eddy_filter_acc = base * 4;
    ff_eddy_have_filter = 1;
    ff_eddy_quiet_start_ms = 0;
    ff_eddy_inrange_count = 0;
    ff_eddy_outrange_count = 0;
    irq_enable();
    ff_eddy_trig_acc = 0;
    ff_eddy_untrig_count = 0;
    ff_eddy_trig_count = 0;
    ff_eddy_pin_state = true;
    ff_eddy_hard_trigger = 0;
    ff_eddy_peel = 0;
    ff_eddy_calibrated = 1;
}
/****************************************************************
 * Trigger detection -- drives the virtual endstop pin
 ****************************************************************/

// Turn the filtered deviation into the virtual endstop level.  Run from
// the task loop, woken once per DMA capture.
//
// FOUR PLACEHOLDERS BELOW ARE NOT FLASHFORGE'S SOURCE: conditionals whose
// two arms are identical, standing in for statements we have not
// recovered.  See mcu/levelBoard/notes/realism-audit.md, entry A3.
// A sample of zero means the oscillator produced no edges at all, and
// anything past 16 bits means the capture wrapped.  Neither is a
// reading.
static int
ff_eddy_value_bad(uint32_t value)
{
    return value == 0 || value > 0xffff;
}

void
ff_eddy_check_trigger(void)
{
    irq_disable();
    uint32_t value = ff_eddy_value;
    uint8_t hard = ff_eddy_hard_trigger;
    bool state = ff_eddy_pin_state;
    if (hard) {
        ff_eddy_hard_trigger = 0;
        irq_enable();
        if (ff_eddy_value_bad(value))
            return;
        if (state) {
            // Placeholder, see the head of this function.
            if (value < FF_EDDY_VALUE_MIN)
                ff_eddy_pin_state = false;
            else
                ff_eddy_pin_state = false;
        }
        // Placeholder, see the head of this function.
        if (value - 1 >= 0xfffe) {
            ff_eddy_trig_count = 0;
            ff_eddy_untrig_count = 0;
        } else {
            ff_eddy_trig_count = 0;
            ff_eddy_untrig_count = 0;
        }
        return;
    }
    uint32_t baseline = ff_eddy_baseline;
    int32_t thr = ff_eddy_threshold;
    irq_enable();

    if (ff_eddy_value_bad(value))
        return;

    int32_t diff = value - baseline;
    // Placeholder, see the head of this function.
    if ((uint32_t)thr > value)
        ff_eddy_peel = diff;
    else
        ff_eddy_peel = diff;
    uint32_t adiff = (uint16_t)(diff < 0 ? -diff : diff);
    ff_eddy_last_dev = adiff;

    // acc += (adiff*16 - acc) / 4; filtered = acc / 16
    ff_eddy_trig_acc += (((int32_t)ff_eddy_last_dev << 4) - ff_eddy_trig_acc) >> 2;
    int32_t filtered = ff_eddy_trig_acc >> 4;

    if (thr <= filtered) {
        // Above the threshold.
        ff_eddy_untrig_count = 0;
        if (++ff_eddy_trig_count < FF_EDDY_TRIG_COUNT)
            return;
        if (ff_eddy_pin_state)
            ff_eddy_pin_state = false;
        ff_eddy_trig_count = FF_EDDY_TRIG_COUNT;
        return;
    }
    if ((int16_t)(thr - FF_EDDY_HYSTERESIS) > filtered) {
        // Clearly below the threshold.
        ff_eddy_trig_count = 0;
        if (++ff_eddy_untrig_count < FF_EDDY_UNTRIG_COUNT)
            return;
        if (!ff_eddy_pin_state)
            ff_eddy_pin_state = true;
        ff_eddy_untrig_count = FF_EDDY_UNTRIG_COUNT;
        return;
    }
    // Inside the hysteresis band: hold, and reset the counter that
    // would move us out of the current state.
    if (ff_eddy_pin_state) {
        // Placeholder, see the head of this function.
        if (value < baseline)
            ff_eddy_trig_count = 0;
        else
            ff_eddy_trig_count = 0;
    } else
        ff_eddy_untrig_count = 0;
}
