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
        /* Code starts on a 16-byte boundary past the vector table.  The
           gap and the input-section order that follows reproduce the
           factory image's .text layout: everything built without
           -ffunction-sections (crtbegin.o, libgcc.a, and libc's
           hand-written assembler) has a plain .text and comes first, then
           the function-sectioned objects.  This is reproduction
           scaffolding; see mcu/levelBoard/notes/ for how it was derived. */
        *(.text)
        *(.text.*)
        /* __libc_init_array() (generic/armcm_startup.S calls it) ends with
           "bl _init", so crti.o/crtn.o's halves of _init and _fini are
           linked, and crtbegin.o's empty .eh_frame is placed alongside
           them, just ahead of the read-only data. */
        *(.eh_frame)
        KEEP(*(.init))
        KEEP(*(.fini))
        *(.rodata .rodata*)
        /* libgcc's one unwind-index entry (EXIDX_CANTUNWIND for
           __udivmoddi4, 8 bytes) belongs between the read-only data and
           the init array; the image is 8 bytes short without it. */
        *(.ARM.exidx*)
        /* GCC's startup files are linked in: __do_global_dtors_aux and
           frame_dummy from crtbegin.o survive --gc-sections only because
           these arrays KEEP them. */
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
        *(.data .data.*);
        . = ALIGN(4);
        _data_end = .;
    } > ram

    .bss (NOLOAD) :
    {
        . = ALIGN(4);
        _bss_start = .;
        /* The list below imposes the factory image's .bss variable order,
           which is neither link order nor alphabetical.  -fdata-sections
           gives every variable its own .bss.<name> input section, so the
           order is set here rather than by moving definitions between
           files.  crtbegin.o's plain .bss comes first, and everything from
           the receive/transmit buffers onward is already in order.  This
           is reproduction scaffolding; see mcu/levelBoard/notes/. */
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
