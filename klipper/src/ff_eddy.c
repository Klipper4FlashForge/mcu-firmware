// FlashForge Creator5 "levelBoard" eddy-current bed probe front end.
//
// Recovered from the stock image work/stock/mcu/levelBoard.bin
// (load address 0x08004000, Cortex-M3 Thumb-2, no symbols).  Every
// non-obvious claim below carries the flash address of the instruction
// that justifies it.  Anything that could not be pinned down is marked
// "UNCERTAIN" rather than guessed at.
//
// What the hardware actually is
// -----------------------------
// There is NO ADC in this module.  The probe is an LC oscillator whose
// frequency is pulled by the steel bed.  The oscillator output is fed
// into TIM8_ETR (PA0, alternate function 8, 0x08007818..0x0800782E) and
// TIM8 is put in external-clock mode 2 with ARR=500, so TIM8 raises an
// update event once every 501 oscillator edges (0x0800783A/0x0800784A).
// TIM1 free-runs off the internal timer clock as a plain 16-bit tick
// counter (PSC=0, ARR=0xffff, 0x0800786E..0x0800787C).  DMA1 channel 1
// is armed circular, one halfword, TIM1->CNT -> a single RAM word, and
// is requested by the TIM8 update (0x08007780..0x080077FA).  So every
// DMA completion interrupt hands us the TIM1 tick count at that moment,
// and the difference between successive captures is
//
//     ticks elapsed while the oscillator produced 501 edges
//
// i.e. a reciprocal frequency (period) measurement, 16 bits wide.  That
// difference is "value" as ff_eddy.py sees it.  Larger value == lower
// oscillator frequency == metal closer.  With CLOCK_FREQ=128000000 one
// tick is 7.8125 ns.
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <stddef.h> // NULL
#include <stdint.h> // uint32_t
#include <string.h> // memcpy
#include "autoconf.h" // CONFIG_CLOCK_FREQ
#include "board/armcm_boot.h" // VectorTable
#include "board/gpio.h" // gpio_out_setup
#include "board/internal.h" // enable_pclock, gpio_peripheral
#include "board/irq.h" // irq_disable
#include "board/misc.h" // timer_read_time
#include "command.h" // DECL_COMMAND
#include "ff_flashforge.h" // ff_eddy_value
#include "n32g45x.h" // NVIC_Init
#include "sched.h" // DECL_TASK

// Number of external oscillator edges per captured sample.
// TIM8->ARR, 0x08007836 (movw r1, #0x1f4) -> update every ARR+1 = 501.
#define FF_EDDY_GATE_ARR 500

// One eddy sample is consumed every 500us by the polling timer
// (0x08006008: mov.w r0, #0x1f4 -> timer_from_us(500)).
#define FF_EDDY_SAMPLE_US 500

// Ring buffer used for the noise statistics.  11 entries: the copy loop
// at 0x08007966 walks &ring[0] .. &ring[0]+0x2c, and the sorted median
// is taken from index 5 (0x080079B8 reads sp+0x18, array base sp+4).
#define FF_EDDY_NSAMP 11

// Deviation (in TIM1 ticks) above which a sample is treated as a gross
// excursion rather than as noise -- 0x080079F4 (cmp r3, #0x96).
#define FF_EDDY_HARD_DEV 150

// Consecutive gross excursions before the endstop is forced to trigger
// -- 0x08007B6C (cmp r3, #0xe -> fires on the 15th).
#define FF_EDDY_HARD_COUNT 15

// Consecutive out-of-threshold samples before the sampling reference is
// dragged to the current reading -- 0x08007A0C (cmp r3, #0x63).
#define FF_EDDY_DRIFT_COUNT 100

// The auto-calibrated threshold is 3*sigma clamped to this range
// -- 0x08007B02 (cmp #0x3c) and 0x08007B0C (cmp #0x14).
#define FF_EDDY_THRESH_MIN 20
#define FF_EDDY_THRESH_MAX 60

// The signal must stay quiet this long before a recalibration is
// accepted -- 0x08007A6A (cmp.w r3, #0x7d0).
#define FF_EDDY_QUIET_MS 2000

// Debounce depths in ff_eddy_check_trigger() -- 0x08007D12 (cmp #3, so
// the 4th consecutive sample trips) and 0x08007D4A (cmp #2, the 3rd
// consecutive sample releases).
#define FF_EDDY_TRIG_COUNT   4
#define FF_EDDY_UNTRIG_COUNT 3

// Hysteresis, in ticks, below the trigger threshold -- 0x08007D36
// (subs r7, #2).
#define FF_EDDY_HYSTERESIS 2


/****************************************************************
 * State
 ****************************************************************/

// Initialised data (.data runs 0x20000000..0x20000044 and is copied
// from flash 0x0800A80C by the reset handler at 0x080088D4).

// Threshold as the host set it.  Written and echoed by
// set_trigger_threshold (0x08004D0A) and read by nothing else.
int32_t ff_trigger_threshold __attribute__((section(".data.ff000"))) = 25;

// Virtual endstop pin level.  1 == not triggered, 0 == triggered.
// gpio_in_read() returns this for one specific pin, see below.
volatile uint8_t ff_eddy_pin_state __attribute__((section(".data.ff101"))) = 1;

// Threshold actually used by the detector.  set_trigger_threshold
// writes it (0x08004D0C) but ff_eddy_update() overwrites it on every
// recalibration (0x08007B14), so a host-supplied value is transient.
int16_t ff_eddy_threshold __attribute__((section(".data.ff102"))) = 25;

// Largest median-absolute-deviation still considered "quiet".
// Never written anywhere in the image; initialiser 0x0800A844 = 2.
static uint32_t ff_eddy_mad_limit __attribute__((section(".data.ff100"))) = 2;

// Zero-initialised data (.bss 0x20000044..0x200003A8, 0x080088EA).

struct timer ff_eddy_timer;                             // 0x20000110
struct task_wake ff_eddy_wake;                          // 0x200000AC
// Set once the first calibration finished; never cleared (0x0800601C).
uint8_t ff_eddy_armed;                                  // 0x200000AD

static uint32_t ff_eddy_prev_cnt;                       // 0x2000012C
static volatile uint32_t ff_eddy_dma_capture;           // 0x20000130
// Written by ff_eddy_check_trigger() (0x08007CEC) and read by nothing.
static volatile uint32_t ff_eddy_last_dev;                       // 0x20000134
// Written by ff_eddy_timer_event() (0x08006030) and read by nothing.
uint32_t ff_eddy_dbg_baseline;                          // 0x20000138
static uint8_t ff_eddy_have_filter;                     // 0x2000013C
// volatile: keeps the seven stores after irq_enable() in
// ff_eddy_rebaseline() (0x08007BF4) in program order, which is the
// only spelling that reproduces stock's store order and register
// colouring there; ff_eddy_check_trigger() and ff_eddy_update()
// compile to the same code with or without it.
static volatile uint8_t ff_eddy_hard_trigger;           // 0x2000013D
static volatile uint32_t ff_eddy_mad;                            // 0x20000140
uint32_t ff_eddy_baseline;                       // 0x20000144
static int32_t ff_eddy_trig_acc;                        // 0x20000148
static uint32_t ff_eddy_filter_acc;                     // 0x2000014C
uint32_t ff_eddy_sample_ref;                            // 0x20000150
static volatile uint32_t ff_eddy_sample;                         // 0x20000154
volatile uint32_t ff_eddy_value;                          // 0x20000158
static volatile uint32_t ff_eddy_sample_ready;          // 0x2000015C
uint8_t ff_eddy_calibrated;                             // 0x20000160
static uint16_t ff_eddy_outrange_count;                 // 0x20000162
static uint32_t ff_eddy_ring[FF_EDDY_NSAMP];            // 0x20000164
static uint8_t ff_eddy_ring_count;                      // 0x20000190
static uint8_t ff_eddy_ring_pos;                        // 0x20000191
static uint16_t ff_eddy_inrange_count;                  // 0x20000192
static uint32_t ff_eddy_quiet_start_ms;                 // 0x20000194
static uint8_t ff_eddy_untrig_count;                    // 0x20000198
// Never written in this image, so effectively a constant zero.  It is
// read at 0x08007AF6 and 0x08007BFC only.
uint32_t ff_eddy_offset;                         // 0x2000019C
// Volatile: the stores after irq_enable() in ff_eddy_rebaseline() keep
// their source order in stock, which only volatile stores guarantee.
static volatile uint8_t ff_eddy_trig_count;             // 0x200001A0
volatile int32_t ff_eddy_peel;                            // 0x200001A4




/****************************************************************
 * Small helpers
 ****************************************************************/

// timer_read_time() is DWT->CYCCNT (0x080086F8) and timer_from_us() is
// "us << 7" (0x080086EC), i.e. exactly 128 ticks/us.  The stock code
// divides the raw clock by 128000 with a reciprocal multiply
// (0x08007A44: 0x10624DD3, then >> 45) to get milliseconds.
static uint32_t
ff_eddy_now_ms(void)
{
    return timer_read_time() / (CONFIG_CLOCK_FREQ / 1000);
}

// 0x080076DC: copy the ring, sort it, return the middle element.
// The copy is a plain loop, not memcpy: GCC turns it into the same
// ldm/stm sequence, but a loop leaves the function pure in GCC's early
// analysis, and the call heuristic does not mark a branch to a pure
// call cold.  That is what keeps ff_eddy_update's smoothing path in
// line rather than out of it.
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

// 0x08007740.  Called by command_endstop_home (0x08005514) and by
// command_endstop_recover_state (0x080055EE): drop the detector back to
// the untriggered state before a homing move starts.
//
// Written as assembly because GCC schedules the equivalent C
// (the six stores in this order) with the pin_state store fifth and one
// extra callee-saved register; stock's schedule is reproduced verbatim
// here so the function keeps stock's 40 bytes and 24-byte literal pool.
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

// Newton iteration, 0x08007A9A..0x08007AB6.  Written in the classic
// r/next form so the result is the loop variable itself: the value
// returned is the register the loop carries, not a second copy.
static uint32_t
ff_eddy_isqrt(uint32_t v)
{
    // unlikely(): the zero guard's probability is inlined into
    // ff_eddy_update, where it sets the count of the shared join block
    // after the iteration.  At the default 34 % that block outranks the
    // saturating 3*MAD arm in bb-reorder's trace order; stock places
    // the 3*MAD arm first (0x08007B84), which needs the guard cold.
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

// 0x08007780.  Note DMA_DeInit() is called first (0x0800778E ->
// 0x08008EA4) which also clears the matching bits in DMA1->IFCR.
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
    nvic.NVIC_IRQChannel = DMA1_Channel1_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority = 0;
    nvic.NVIC_IRQChannelSubPriority = 7;
    nvic.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&nvic);
    DMA_ConfigInt(NS_DMA1_CH1, DMA_INT_TXC);
    DMA_EnableChannel(NS_DMA1_CH1);
}

// 0x08007808.  Runs before ff_eddy_dma_init(), which it tail calls
// (0x08007886).
void
ff_eddy_counter_init(void)
{
    RCC_EnableAPB2PeriphClk(0x2000);
    {
        // The struct lives in its own scope: with an addressable local
        // in the outer scope GCC will not turn the ff_eddy_dma_init()
        // below into the tail call stock has at 0x08007886.
        GPIO_InitType gpio;
        GPIO_InitStruct(&gpio);
        gpio.Pin = 1;
        gpio.GPIO_Mode = GPIO_MODE_AF_PP;
        gpio.GPIO_Current = 2;      // 8mA drive, 0x08007826
        gpio.GPIO_Alternate = 8;    // TIM8_ETR, 0x0800782C
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

// 0x08007894.  Vector 27 (IRQ 11).
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
    sched_wake_task(&ff_eddy_wake);             // 0x080078CC
}
DECL_ARMCM_IRQ(DMA1_Channel1_IRQHandler, 11);


/****************************************************************
 * Sample processing and auto calibration
 ****************************************************************/

// 0x080078EC.  Called from the 500us polling timer, not from the DMA
// interrupt, so at most one sample is consumed per 500us regardless of
// how fast the oscillator runs.
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
        // 0x080079D0.  The two comparisons are written this way round
        // because stock tests the threshold first and the 150-tick
        // ceiling in both arms of it (0x080079F4 and 0x08007B40).
        // adev is a PHI of two uint16 conversions, so phiopt does not
        // fold it into ABS_EXPR and combine reuses the subtraction's
        // flags for the sign test (0x080079D8).
        int32_t dev = ff_eddy_sample - ff_eddy_sample_ref;
        uint16_t adev = dev < 0 ? (uint16_t)-dev : (uint16_t)dev;
        int32_t thr = ff_eddy_threshold;
        uint16_t athr = thr < 0 ? -thr : thr;

        if (adev > athr && adev <= FF_EDDY_HARD_DEV) {
            // Beyond the threshold but not wildly so: this is what a
            // real probe touch looks like.  Feed the *baseline* to the
            // statistics so a trigger does not pollute the noise
            // estimate (0x08007A04).  The baseline load and the
            // counter increment sit before the compare so tree-ssa-sink
            // keeps them in this block instead of sinking them.
            store = ff_eddy_baseline;
            ff_eddy_inrange_count++;
            ff_eddy_outrange_count = 0;
            if (ff_eddy_inrange_count > FF_EDDY_DRIFT_COUNT - 1) {
                // Stuck off-baseline for 100 samples: assume drift and
                // move the reference (0x08007A18..0x08007A20).
                ff_eddy_inrange_count = 0;
                uint32_t v = ff_eddy_sample;
                ff_eddy_baseline = v;
                ff_eddy_sample_ref = v;
                store = ff_eddy_sample;
            }
        } else if (adev > FF_EDDY_HARD_DEV) {
            // Gross excursion.  Still fed raw, but after a run of them
            // the endstop is forced to trigger (0x08007B5E).
            store = ff_eddy_sample;
            if (++ff_eddy_outrange_count > FF_EDDY_HARD_COUNT - 1) {
                ff_eddy_hard_trigger = 1;       // 0x08007B7A
                ff_eddy_outrange_count = 0;
            }
        } else {
            // Quiet: feed the raw reading to the statistics.
            ff_eddy_inrange_count = 0;
            ff_eddy_outrange_count = 0;
            store = ff_eddy_sample;
        }
    }

    // --- common tail, 0x08007912 ---
    ff_eddy_sample_ready = 0;
    ff_eddy_ring[ff_eddy_ring_pos] = store;
    ff_eddy_ring_pos++;
    // unlikely() makes the fall-through edge hot enough that the
    // ring_pos store stays here rather than being sunk.
    if (unlikely(ff_eddy_ring_pos > FF_EDDY_NSAMP - 1))
        ff_eddy_ring_pos = 0;
    if (ff_eddy_ring_count <= FF_EDDY_NSAMP - 1)
        ff_eddy_ring_count++;

    // Seed the smoothing filter once the ring is full (0x08007A28).
    // The early return on !have_filter gives the smoothing path the
    // predictor's 66% and puts &filter_acc, not &have_filter, in r9.
    if (!ff_eddy_have_filter) {
        if (ff_eddy_ring_count == FF_EDDY_NSAMP) {
            ff_eddy_filter_acc = ff_eddy_median() * 4;
            ff_eddy_have_filter = 1;
            ff_eddy_quiet_start_ms = ff_eddy_now_ms();
        }
        return;
    }

    // Smoothing filter, held at 4x scale: acc = x + 3*acc/4, so
    // acc/4 is a first order low pass with alpha = 1/4 (0x08007950).
    ff_eddy_filter_acc = store + (ff_eddy_filter_acc * 3) / 4;

    // Robust noise estimate: median absolute deviation about the
    // median of the ring (0x0800795C..0x080079BA).
    uint32_t center = ff_eddy_median();
    uint32_t devs[FF_EDDY_NSAMP];
    uint32_t i;
    for (i = 0; i < FF_EDDY_NSAMP; i++) {
        uint32_t s = ff_eddy_ring[i];
        devs[i] = s >= center ? s - center : center - s;
    }
    // Insertion sort; the inner compare reads through a named cur so
    // the key is the first operand by SSA version order.
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
    // A dead conditional on ff_eddy_ring_pos.  Both arms store the same
    // value, so it does nothing at run time, and it costs no bytes: the
    // arms are cross-jumped after reload and the load and compare are
    // then deleted.  What it does is keep a reference to
    // &ff_eddy_ring_pos alive into IRA, which lifts that allocno above
    // the (mad, lim) thread in the colouring order and gives stock's r6
    // and r7 across the whole function.
    //
    // Stock has such a conditional; its text cannot be recovered,
    // because every trace of it is gone by the time the compiler emits
    // code.  What is pinned is the class: the condition must read
    // ring_pos, must be one GCC cannot fold (a ternary folds and loses
    // the match), and both arms must be identical (any arm that does
    // real work emits real code).  A bounds check whose arms were
    // filled in the same by mistake fits, and is the likeliest reading:
    // it would be invisible in testing, since the scrub below has no
    // observable effect either.
    if (ff_eddy_ring_pos)
        ff_eddy_mad = mad;
    else
        ff_eddy_mad = mad;

    if (ff_eddy_mad_limit < mad) {
        // Noisy: restart the quiet timer (0x080079C4).
        ff_eddy_quiet_start_ms = 0;
        return;
    }
    uint32_t now = ff_eddy_now_ms();
    // No return here: an explicit return that is not the function's
    // last statement carries the gimplifier's early-return prediction
    // (66 %), and the probabilities that sets decide which address IRA
    // keeps in r9 and where bb-reorder copies the epilogue.
    if (!ff_eddy_quiet_start_ms)
        ff_eddy_quiet_start_ms = now;           // 0x08007B56
    if (now - ff_eddy_quiet_start_ms < FF_EDDY_QUIET_MS)
        return;

    // --- 2s of quiet: recalibrate (0x08007A70..0x08007B3A) ---
    uint64_t sumsq = 0;
    for (i = 0; i < FF_EDDY_NSAMP; i++) {
        int32_t d = ff_eddy_ring[i] - center;
        sumsq += (int32_t)(d * d);
    }
    uint32_t sd = ff_eddy_isqrt((uint32_t)(sumsq / FF_EDDY_NSAMP));

    // Never let sigma fall below 1.5 * MAD (and never below 1).
    // The floor is computed as a signed temporary and then converted:
    // the conversion gives the floor its own SSA name, separate from
    // the add, which is what yields stock's r1/r2 assignment in the
    // floor/clamp block at 0x08007A98..0x08007B38.  The value is the
    // same either way (modulo conversion), and the compare below stays
    // unsigned.
    int32_t mad3over2 = mad + mad / 2;
    uint32_t floor_sd = mad3over2;
    if (floor_sd < 1)
        floor_sd = 1;
    if (sd < floor_sd)
        sd = floor_sd;

    // Scrub outliers out of the ring.  NOTE: this has no observable
    // effect, because ff_eddy_ring_count/pos are reset a few lines
    // below and every slot is overwritten before it is read again.
    if (ff_eddy_ring_count) {
        uint32_t lim;
        // mad != 0 first: bb-reorder's prev_bb tie-break then places
        // the mad_limit block after the saturating arm.
        if (mad) {
            // Saturating 3*MAD, 0x08007B84.
            uint64_t t = (uint64_t)mad * 3;
            if (t > 0xffffffffull)
                lim = 0xffffffffu;
            else
                lim = mad * 3;
        } else {
            lim = ff_eddy_mad_limit;            // 0x08007AD2
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
    // Clamp min first, then max (0x08007B0C).
    int16_t thr = (int16_t)(sd * 3);
    if (thr < FF_EDDY_THRESH_MIN)
        thr = FF_EDDY_THRESH_MIN;
    if (thr >= FF_EDDY_THRESH_MAX)
        thr = FF_EDDY_THRESH_MAX;
    ff_eddy_threshold = thr;

    ff_eddy_baseline = ff_eddy_offset + ff_eddy_filter_acc / 4;
    ff_eddy_sample_ref = ff_eddy_baseline;
    ff_eddy_have_filter = 0;
    // calibrated is stored right after have_filter: sched2 emits these
    // independent plain stores in source order, and this position gives
    // stock's r0/r1 naming for &have_filter/&quiet_start_ms and the
    // placement of its "movs r1, #1".
    ff_eddy_calibrated = 1;
    ff_eddy_ring_count = 0;
    ff_eddy_ring_pos = 0;
    ff_eddy_quiet_start_ms = 0;
    ff_eddy_inrange_count = 0;
    ff_eddy_outrange_count = 0;
    // Falls off the end: recalibration is the function's last block.
}

/****************************************************************
 * Host commands
 ****************************************************************/

// 0x08007BF4.  Called by get_basic_param; re-zeroes everything against
// the current reading and declares the sensor calibrated.
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
    // This store order is what GCC's sched1 pressure model plus IRA
    // need to reproduce stock's store order and register colouring at
    // 0x08007BF4: calibrated last so its address takes r3.
    ff_eddy_trig_acc = 0;
    ff_eddy_untrig_count = 0;
    ff_eddy_trig_count = 0;
    ff_eddy_pin_state = 1;
    ff_eddy_hard_trigger = 0;
    ff_eddy_peel = 0;
    ff_eddy_calibrated = 1;
}
/****************************************************************
 * Trigger detection -- drives the virtual endstop pin
 ****************************************************************/

// 0x08007C98.  Woken once per DMA capture by DMA1_Channel1_IRQHandler.
// In the stock image the sched_check_wake()/call pair is open coded at
// the bottom of run_tasks() (0x080063BA..0x080063C6) rather than being
// dispatched through ctr_run_taskfuncs(); the effect is the same.
void
// This function is byte-exact, but read the four dead conditionals below
// with suspicion.  Each emits nothing and exists only to adjust how often
// `value`, `value - 1`, `thr` or `baseline` is referenced, which is what
// decides the register assignment here.  One such construct in a function
// is a believable slip; four is not, and the other exact functions needed
// none or one.  So this reproduces stock's bytes without being stock's
// source.  They are most likely not four separate slips but one structural
// error of ours, patched in four places.  Two pieces of evidence for that:
// dropping the hysteresis-tail conditional changes this function's *size*
// by four bytes, which no register choice can do, so that one is buying a
// code shape rather than a colouring; and stock's two range checks use
// opposite register pairs (hard arm `subs r3,r5,#1 / movw r2,#0xfffe`,
// main arm the reverse), while the source below produces the main arm's
// shape in both, so stock's hard arm holds something not reconstructed
// here.  Ruled out as the missing piece: computing the absolute deviation
// by subtraction order rather than negation, in any combination (it
// reaches `sub`, never stock's `neg`); the range check spelled as
// `value == 0 || value > 0xffff` or `value - 1 >= 0xffff`; nesting the
// hard arm instead of returning early; reordering the counter stores.
// Treat the bytes as settled and the spelling as not.
ff_eddy_check_trigger(void)
{
    irq_disable();
    uint32_t value = ff_eddy_value;
    uint8_t hard = ff_eddy_hard_trigger;
    uint8_t state = ff_eddy_pin_state;
    if (hard) {
        ff_eddy_hard_trigger = 0;
        irq_enable();
        // Reject value 0 (no oscillator edges at all).
        if (value - 1 > 0xfffe)
            return;
        if (state) {
            // Another dead conditional, both arms storing 0, emitting
            // nothing.  It gives `value` a use past the range test, so
            // `value` and `value - 1` keep separate live ranges: the
            // subtraction lands in a call-clobbered register after
            // irq_enable(), as in stock, rather than being folded into
            // `value` ahead of the call.  This placement, around the
            // pin-state store, is the only one that costs no bytes.
            // The condition must not be provably constant: a bare
            // `if (value)` is deleted before IRA and does nothing.
            if (value == 1)
                ff_eddy_pin_state = 0;
            else
                ff_eddy_pin_state = 0;
        }
        // A third dead conditional, arms identical.  Its condition is a
        // second use of `value - 1`, which raises that allocno's
        // frequency past the constant it is tied with, so it sorts
        // ahead in IRA's colourable bucket and pops into r3 first, as
        // in stock.  It must not be foldable: `> 0xfffe`, the same
        // condition as the guard above, is proved false by VRP and
        // deleted.
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

    if (value - 1 > 0xfffe)
        return;

    int32_t diff = value - baseline;
    // A dead conditional, as in ff_eddy_update: both arms store the same
    // value, so the arms are cross-jumped and the compare deleted, and
    // it emits nothing.  It does two things.  Reading `value` here keeps
    // it live past the subtraction, which breaks the shuffle copy that
    // would otherwise join the difference to `value`'s allocno thread,
    // and makes the peel, negate and trig_acc chain byte-exact.  Reading
    // `thr` rather than `baseline` puts this block's weight on `thr`:
    // IRA drops r0-r3 from an allocno's profitable set once the cost of
    // preserving it across irq_enable() exceeds its memory cost, which
    // is its own frequency-weighted reference count, so the hot
    // reference decides which of `thr` and `baseline` is constrained,
    // and so which takes r4.  This is the hottest block, and putting it
    // on `thr` gives stock's assignment.
    if (value == (uint32_t)thr)
        ff_eddy_peel = diff;                    // 0x08007CE0
    else
        ff_eddy_peel = diff;
    uint32_t adiff = (uint16_t)(diff < 0 ? -diff : diff);
    ff_eddy_last_dev = adiff;                   // write only

    // acc += (adiff*16 - acc) / 4; filtered = acc / 16   (0x08007CF2)
    ff_eddy_trig_acc += (((int32_t)ff_eddy_last_dev << 4) - ff_eddy_trig_acc) >> 2;
    int32_t filtered = ff_eddy_trig_acc >> 4;

    if (thr <= filtered) {
        // Above the threshold.
        ff_eddy_untrig_count = 0;
        if (++ff_eddy_trig_count <= FF_EDDY_TRIG_COUNT - 1)
            return;
        if (ff_eddy_pin_state)
            ff_eddy_pin_state = 0;
        ff_eddy_trig_count = FF_EDDY_TRIG_COUNT;
        return;
    }
    if ((int16_t)(thr - FF_EDDY_HYSTERESIS) > filtered) {
        // Clearly below the threshold.
        ff_eddy_trig_count = 0;
        if (++ff_eddy_untrig_count <= FF_EDDY_UNTRIG_COUNT - 1)
            return;
        if (!ff_eddy_pin_state)
            ff_eddy_pin_state = 1;
        ff_eddy_untrig_count = FF_EDDY_UNTRIG_COUNT;
        return;
    }
    // Inside the hysteresis band: hold, and reset the counter that
    // would move us out of the current state (0x08007D60).
    if (ff_eddy_pin_state) {
        // `baseline` needs one reference after the subtraction, or IRA
        // makes it die there and lends its register to the difference,
        // which costs two instructions.  This one is cold enough to
        // leave its memory cost below the caller-save threshold.  The
        // store it wraps has to be volatile: around a plain store,
        // GIMPLE tail-merge deletes the conditional before IRA sees it.
        if (value == baseline)
            ff_eddy_trig_count = 0;
        else
            ff_eddy_trig_count = 0;
    } else
        ff_eddy_untrig_count = 0;
}
