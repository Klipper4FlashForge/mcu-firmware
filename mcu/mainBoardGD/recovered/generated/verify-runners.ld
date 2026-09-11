SECTIONS {
    .ctr_run_initfuncs 0x27c8 : { *(.text.ctr_run_initfuncs) }
    .ctr_run_shutdownfuncs 0x27e8 : { *(.text.ctr_run_shutdownfuncs) }
    .ctr_run_taskfuncs 0x2810 : { *(.text.ctr_run_taskfuncs) }
    .ARM.exidx : { *(.ARM.exidx*) }
}
PROVIDE(alloc_init = 0x000007a9);
PROVIDE(analog_in_shutdown = 0x00000869);
PROVIDE(analog_in_task = 0x000008d1);
PROVIDE(buttons_task = 0x00000a59);
PROVIDE(clear_active_irq = 0x00000b11);
PROVIDE(console_task = 0x000020d9);
PROVIDE(digital_out_shutdown = 0x00002989);
PROVIDE(initial_pins_setup = 0x00003879);
PROVIDE(irq_poll = 0x00003891);
PROVIDE(mclib_init = 0x00003d01);
PROVIDE(move_reset = 0x00003ed9);
PROVIDE(sendf_shutdown = 0x00004519);
PROVIDE(serial_init = 0x000045a1);
PROVIDE(stepper_shutdown = 0x000048b1);
PROVIDE(timer_cnt_init = 0x00004ec9);
PROVIDE(timer_reset = 0x00005591);
PROVIDE(timer_task = 0x00005869);
PROVIDE(trsync_shutdown = 0x000059d1);
PROVIDE(trsync_task = 0x00005a41);
