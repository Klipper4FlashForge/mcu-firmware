// Generic ARM Cortex-M linker script
//
// Copyright (C) 2019  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h" // CONFIG_FLASH_APPLICATION_ADDRESS

OUTPUT_FORMAT("elf32-littlearm", "elf32-littlearm", "elf32-littlearm")
OUTPUT_ARCH(arm)

MEMORY
{
  rom (rx) : ORIGIN = CONFIG_FLASH_APPLICATION_ADDRESS , LENGTH = CONFIG_FLASH_SIZE
  ram (rwx) : ORIGIN = CONFIG_RAM_START , LENGTH = CONFIG_RAM_SIZE
}

SECTIONS
{
    .text : {
        . = ALIGN(4);
        _text_vectortable_start = .;
        KEEP(*(.vector_table))
        _text_vectortable_end = .;
        /* Stock starts code at 0x08004120, twelve bytes past the end of its
           69-word vector table, and puts libgcc first: __udivmoddi4 sits at
           0x0800418C, ahead of the first command handler at 0x08004540. */
        . = ALIGN(16);
        /* Stock's text order falls straight out of "plain .text first,
           function-sections second".  Everything built without
           -ffunction-sections has a plain .text: crtbegin.o, all of
           libgcc.a, and the hand-written assembler in libc (memchr.S,
           setjmp.S, strcmp.S).  So 0x08004120..0x08004540 is
           __do_global_dtors_aux, frame_dummy, __aeabi_uldivmod,
           __udivmoddi4, __aeabi_ldiv0, memchr, setjmp, longjmp, strcmp --
           in link order crtbegin, -lgcc, -lc_nano -- and only then do the
           application objects begin, with command_config_analog_in at
           0x08004540.  libc's C files (__libc_init_array, memcmp, memcpy,
           memmove, memset) are function-sectioned and land at the end,
           which is where stock has them (0x08009044..0x0800910C). */
        *(.text)
        *(.text.*)
        /* __libc_init_array() (generic/armcm_startup.S calls it) ends with
           "bl _init", so crti.o/crtn.o's halves of _init and _fini are
           linked.  Stock has them right after memset, at 0x0800910C and
           0x08009118, ahead of the read-only data. */
        /* crtbegin.o's empty .eh_frame sits here in stock: the frame
           address that frame_dummy and __do_global_dtors_aux keep in their
           literal pools is 0x0800910C, the same address as _init. */
        *(.eh_frame)
        KEEP(*(.init))
        KEEP(*(.fini))
        *(.rodata .rodata*)
        /* Stock keeps libgcc's one unwind-index entry (EXIDX_CANTUNWIND for
           __udivmoddi4, 8 bytes) between the read-only data and the init
           array; the image ends 8 bytes short without it. */
        *(.ARM.exidx*)
        /* Stock links GCC's startup files: __do_global_dtors_aux and
           frame_dummy from crtbegin.o sit at 0x08004120, ahead of libgcc.
           They survive --gc-sections only because these arrays KEEP them. */
        . = ALIGN(4);
        PROVIDE_HIDDEN(__preinit_array_start = .);
        KEEP(*(.preinit_array))
        PROVIDE_HIDDEN(__preinit_array_end = .);
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT(.init_array.*)))
        KEEP(*(.init_array))
        PROVIDE_HIDDEN(__init_array_end = .);
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT(.fini_array.*)))
        KEEP(*(.fini_array))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } > rom

    . = ALIGN(4);
    _data_flash = .;

#if CONFIG_ARMCM_RAM_VECTORTABLE
    .ram_vectortable (NOLOAD) : {
        _ram_vectortable_start = .;
        . = . + ( _text_vectortable_end - _text_vectortable_start ) ;
        _ram_vectortable_end = .;
    } > ram
#endif

    .data : AT (_data_flash)
    {
        . = ALIGN(4);
        _data_start = .;
        *(.ramfunc .ramfunc.*);
        KEEP(*(.data.ff000))
        *(.data)
        *(EXCLUDE_FILE (*ff_eddy.o *system_stm32f1xx.o) .data.*)
        KEEP(*(.data.ff100 .data.ff101 .data.ff102 .data.ff103))
        /* SystemCoreClock is the last initialised variable, 0x20000040. */
        *system_stm32f1xx.o(.data .data.*)
        . = ALIGN(4);
        _data_end = .;
    } > ram

    .bss (NOLOAD) :
    {
        . = ALIGN(4);
        _bss_start = .;
        /* Stock's variable order, read off the image from the literal
           pools of instruction-exact functions.  It is neither link order
           nor alphabetical: sched.c's shutdown_jmp sits between the eddy
           sensor's wake flag and its timer, and ff_shutdown_code between
           tmcuart's and trsync's wake flags.  -fdata-sections gives every
           variable its own .bss.<name> input section, so the order is
           imposed here rather than by moving definitions between files.
           crtbegin.o's plain .bss (completed.1, object.0) comes first,
           and the receive/transmit buffers onward are already in order. */
        *(.bss)
        *(.bss.analog_in_value)
        *(.bss.analog_wake)
        *(.bss.alloc_end)
        *(.bss.config_crc)
        *(.bss.count.2)
        *(.bss.move_count)
        *(.bss.move_free_list)
        *(.bss.move_item_size)
        *(.bss.move_list)
        *(.bss.oid_count)
        *(.bss.oids)
        *(.bss.stats_send_time)
        *(.bss.stats_send_time_high)
        *(.bss.sum.1)
        *(.bss.sumsq.0)
        *(.bss.buttons_wake)
        *(.bss.in_sendf)
        *(.bss.sync_state.0)
        *(.bss.ff_endstop_active)
        *(.bss.counter_wake)
        *(.bss.ff_close_num)
        *(.bss.ff_temp_waketime)
        *(.bss.ff_eddy_wake)
        *(.bss.ff_eddy_armed)
        *(.bss.shutdown_jmp)
        *(.bss.ff_timer_close)
        *(.bss.ff_eddy_timer)
        *(.bss.task_start)
        *(.bss.tmcuart_wake)
        *(.bss.ff_shutdown_code)
        *(.bss.trsync_wake)
        *(.bss.ff_eddy_prev_cnt)
        *(.bss.ff_eddy_dma_capture)
        *(.bss.ff_eddy_last_dev)
        *(.bss.ff_eddy_dbg_baseline)
        *(.bss.ff_eddy_have_filter)
        *(.bss.ff_eddy_hard_trigger)
        *(.bss.ff_eddy_mad)
        *(.bss.ff_eddy_baseline)
        *(.bss.ff_eddy_trig_acc)
        *(.bss.ff_eddy_filter_acc)
        *(.bss.ff_eddy_sample_ref)
        *(.bss.ff_eddy_sample)
        *(.bss.ff_eddy_value)
        *(.bss.ff_eddy_sample_ready)
        *(.bss.ff_eddy_calibrated)
        *(.bss.ff_eddy_outrange_count)
        *(.bss.ff_eddy_ring)
        *(.bss.ff_eddy_ring_count)
        *(.bss.ff_eddy_ring_pos)
        *(.bss.ff_eddy_inrange_count)
        *(.bss.ff_eddy_quiet_start_ms)
        *(.bss.ff_eddy_untrig_count)
        *(.bss.ff_eddy_offset)
        *(.bss.ff_eddy_trig_count)
        *(.bss.ff_eddy_peel)
        *(.bss.tx_dma_active)
        *(.bss.*)
        *(COMMON)
        . = ALIGN(4);
        _bss_end = .;
    } > ram

    _stack_start = CONFIG_RAM_START + CONFIG_RAM_SIZE - CONFIG_STACK_SIZE ;
    .stack _stack_start (NOLOAD) :
    {
        . = . + CONFIG_STACK_SIZE;
        _stack_end = .;
    } > ram

    /DISCARD/ : {
        // Don't include exception tables
        *(.ARM.extab)
    }
}
