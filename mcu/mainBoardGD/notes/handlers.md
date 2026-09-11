# mainBoardGD command handlers

Walked from `command_index[]` at ITCM `0x6560` -- 50 entries of 16 bytes,
`{uint16 encoded_msgid; uint8 num_args, flags, num_params; const uint8
*param_types; void (*func)(uint32_t *)}`. Handler addresses are ITCM
addresses, which is where they run; in the file they sit at
`address + 0x08004418`.

`tools/klip_cmdtab.py` finds and resolves the same table -- all 49 of 49 --
once the ITCM region is a file of its own; against the raw image it reports
`no command_index found`, which is the layout problem in one line:

    ./tools/scatterload.py mcu/mainBoardGD/stock/mainBoardGD.bin 0x08000000 --out work/regions
    ./tools/klip_cmdtab.py work/regions/00000000.bin work/mainBoardGD.dict.json 0x00000000

| id | command | handler | args | flags |
|---:|---|---|---:|---|
| 1 | `identify` | `0x001840` | 2 | 0x01 |
| 2 | `get_mcu_version` | `0x001778` | 0 | 0x00 |
| 3 | `get_basic_param` | `0x001690` | 1 | 0x00 |
| 4 | `pa_action` | `0x001a08` | 2 | 0x00 |
| 5 | `get_emcu_pa_value` | `0x0017c0` | 0 | 0x00 |
| 6 | `remove_peel` | `0x001c18` | 1 | 0x00 |
| 7 | `clear_shutdown` | `0x000d10` | 0 | 0x01 |
| 8 | `emergency_stop` | `0x0011c0` | 0 | 0x01 |
| 9 | `get_uptime` | `0x0017f0` | 0 | 0x01 |
| 10 | `get_clock` | `0x0016c8` | 0 | 0x01 |
| 11 | `finalize_config` | `0x001460` | 1 | 0x00 |
| 12 | `get_config` | `0x0016f8` | 0 | 0x01 |
| 13 | `allocate_oids` | `0x000b30` | 1 | 0x00 |
| 14 | `debug_nop` | `0x000fa0` | 0 | 0x01 |
| 15 | `debug_ping` | `0x000fa8` | 2 | 0x01 |
| 16 | `debug_write` | `0x001028` | 3 | 0x01 |
| 17 | `debug_read` | `0x000fd8` | 2 | 0x01 |
| 18 | `set_digital_out` | `0x001ce0` | 2 | 0x00 |
| 19 | `update_digital_out` | `0x001f80` | 2 | 0x00 |
| 20 | `queue_digital_out` | `0x001a88` | 3 | 0x00 |
| 21 | `set_digital_out_pwm_cycle` | `0x001cf8` | 2 | 0x00 |
| 22 | `config_digital_out` | `0x000da8` | 5 | 0x00 |
| 23 | `stepper_stop_on_trigger` | `0x001e08` | 2 | 0x00 |
| 24 | `stepper_get_position` | `0x001da8` | 1 | 0x00 |
| 25 | `reset_step_clock` | `0x001c28` | 2 | 0x00 |
| 26 | `set_next_step_dir` | `0x001d70` | 2 | 0x00 |
| 27 | `queue_step` | `0x001b58` | 4 | 0x00 |
| 28 | `config_stepper` | `0x000f08` | 5 | 0x00 |
| 29 | `endstop_query_state` | `0x0013d0` | 1 | 0x00 |
| 30 | `endstop_home` | `0x001360` | 8 | 0x00 |
| 31 | `config_endstop` | `0x000e08` | 3 | 0x00 |
| 32 | `trsync_trigger` | `0x001ee8` | 2 | 0x00 |
| 33 | `trsync_set_timeout` | `0x001e38` | 2 | 0x00 |
| 34 | `trsync_start` | `0x001e78` | 4 | 0x00 |
| 35 | `config_trsync` | `0x000f78` | 1 | 0x00 |
| 36 | `query_analog_in` | `0x001a28` | 8 | 0x00 |
| 37 | `config_analog_in` | `0x000d18` | 2 | 0x00 |
| 38 | `buttons_ack` | `0x000bb8` | 2 | 0x00 |
| 39 | `buttons_query` | `0x000c90` | 5 | 0x00 |
| 40 | `buttons_add` | `0x000c20` | 4 | 0x00 |
| 41 | `config_buttons` | `0x000d58` | 2 | 0x00 |
| 42 | `reset` | `0x001c20` | 0 | 0x01 |
| 43 | `mclib_set_resonance_damp` | `0x0019a8` | 5 | 0x00 |
| 44 | `mclib_identify_motor` | `0x001900` | 3 | 0x00 |
| 45 | `mclib_set_pid_params` | `0x001960` | 3 | 0x00 |
| 46 | `mclib_set_current` | `0x001910` | 3 | 0x00 |
| 47 | `mclib_config_stalldetect` | `0x0018d0` | 2 | 0x00 |
| 48 | `mclib_config_microstep` | `0x0018a8` | 3 | 0x00 |
| 49 | `config_mclib` | `0x000e40` | 5 | 0x00 |
