#!/usr/bin/env python3
"""GD32H7xx standard peripheral library functions the stock image links.

These are GigaDevice's own sources (recovered/lib/gd32h7xx, V1.1.0), compiled
one file per unit exactly as the original build did. A row here replaces the
hand reconstruction of the same span; the unit owns every function the file
defines, and the ones stock does not link are discarded at link time as
armlink's unused-section elimination would. Names are the SDK's.
"""
UNITS = {'sdk_timer': ('lib/gd32h7xx/Source/gd32h7xx_timer.c', []),
         'sdk_misc': ('lib/gd32h7xx/Source/gd32h7xx_misc.c', []),
         'sdk_adc': ('lib/gd32h7xx/Source/gd32h7xx_adc.c', []),
         'sdk_dma': ('lib/gd32h7xx/Source/gd32h7xx_dma.c', []),
         'sdk_gpio': ('lib/gd32h7xx/Source/gd32h7xx_gpio.c', []),
         'sdk_rcu': ('lib/gd32h7xx/Source/gd32h7xx_rcu.c', []),
         'sdk_usart': ('lib/gd32h7xx/Source/gd32h7xx_usart.c', [])}
LIBRARY_UNITS = set(UNITS)
CASES = [
    # gd32h7xx_timer.c
    ('timer_deinit', 0x4f28, 504, 'sdk_timer'),
    ('timer_struct_para_init', 0x5850, 20, 'sdk_timer'),
    ('timer_init', 0x5138, 448, 'sdk_timer'),
    ('timer_enable', 0x5120, 10, 'sdk_timer'),
    ('timer_channel_output_config', 0x4a10, 820, 'sdk_timer'),
    ('timer_channel_output_mode_config', 0x4d48, 104, 'sdk_timer'),
    ('timer_channel_output_shadow_config', 0x4dd8, 94, 'sdk_timer'),
    ('timer_channel_output_pulse_value_config', 0x4db0, 34, 'sdk_timer'),
    ('timer_channel_output_state_config', 0x4e38, 126, 'sdk_timer'),
    ('timer_channel_output_struct_para_init', 0x4eb8, 10, 'sdk_timer'),
    ('timer_channel_additional_compare_value_config', 0x4980, 14, 'sdk_timer'),
    ('timer_channel_additional_output_shadow_config', 0x4990, 104, 'sdk_timer'),
    ('timer_channel_composite_pwm_mode_config', 0x49f8, 24, 'sdk_timer'),
    ('timer_primary_output_config', 0x5568, 18, 'sdk_timer'),
    ('timer_master_output0_trigger_source_select', 0x5538, 12, 'sdk_timer'),
    ('timer_master_slave_mode_config', 0x5548, 28, 'sdk_timer'),
    ('timer_input_trigger_source_select', 0x52f8, 540, 'sdk_timer'),
    ('timer_slave_mode_select', 0x55a0, 682, 'sdk_timer'),
    # gd32h7xx_misc.c
    ('nvic_priority_group_set', 0x08002078, 20, 'sdk_misc'),
    ('nvic_irq_enable', 0x08002010, 102, 'sdk_misc'),
    ('mpu_region_config', 0x08001f88, 78, 'sdk_misc'),
    ('mpu_region_enable', 0x08001fd8, 18, 'sdk_misc'),
    ('mpu_region_struct_para_init', 0x08001ff0, 26, 'sdk_misc'),
    ('nvic_vector_table_set', 0x08002090, 28, 'sdk_misc'),
    # gd32h7xx_adc.c
    ('adc_calibration_enable', 0x2b0, 32, 'sdk_adc'),
    ('adc_calibration_mode_config', 0x2d0, 32, 'sdk_adc'),
    ('adc_calibration_number', 0x2f0, 16, 'sdk_adc'),
    ('adc_channel_length_config', 0x300, 70, 'sdk_adc'),
    ('adc_clock_config', 0x348, 40, 'sdk_adc'),
    ('adc_data_alignment_config', 0x370, 32, 'sdk_adc'),
    ('adc_deinit', 0x390, 72, 'sdk_adc'),
    ('adc_dma_mode_enable', 0x3d8, 10, 'sdk_adc'),
    ('adc_dma_request_after_last_enable', 0x3e8, 10, 'sdk_adc'),
    ('adc_enable', 0x3f8, 18, 'sdk_adc'),
    ('adc_external_trigger_config', 0x410, 46, 'sdk_adc'),
    ('adc_inserted_channel_config', 0x440, 140, 'sdk_adc'),
    ('adc_interrupt_enable', 0x4d0, 8, 'sdk_adc'),
    ('adc_interrupt_flag_clear', 0x4d8, 6, 'sdk_adc'),
    ('adc_interrupt_flag_get', 0x4e0, 150, 'sdk_adc'),
    ('adc_regular_channel_config', 0x578, 402, 'sdk_adc'),
    ('adc_resolution_config', 0x710, 52, 'sdk_adc'),
    ('adc_special_function_config', 0x748, 92, 'sdk_adc'),
    # gd32h7xx_dma.c
    ('dma_channel_enable', 0x2a40, 18, 'sdk_dma'),
    ('dma_circulation_enable', 0x2a58, 18, 'sdk_dma'),
    ('dma_deinit', 0x2a70, 88, 'sdk_dma'),
    ('dma_flag_clear', 0x2ac8, 56, 'sdk_dma'),
    ('dma_interrupt_enable', 0x2b00, 38, 'sdk_dma'),
    ('dma_interrupt_flag_clear', 0x2b28, 56, 'sdk_dma'),
    ('dma_interrupt_flag_get', 0x2b60, 300, 'sdk_dma'),
    ('dma_single_data_mode_init', 0x2c90, 228, 'sdk_dma'),
    # gd32h7xx_gpio.c
    ('gpio_af_set', 0x3010, 108, 'sdk_gpio'),
    ('gpio_mode_set', 0x3158, 82, 'sdk_gpio'),
    ('gpio_output_options_set', 0x3780, 72, 'sdk_gpio'),
    # gd32h7xx_rcu.c
    ('rcu_periph_clock_enable', 0x080028f0, 28, 'sdk_rcu'),
    ('rcu_periph_reset_enable', 0x08002930, 28, 'sdk_rcu'),
    ('rcu_periph_reset_disable', 0x08002910, 30, 'sdk_rcu'),
    ('rcu_clock_freq_get', 0x08002158, 1944, 'sdk_rcu'),
    # gd32h7xx_usart.c
    ('usart_stop_bit_set', 0x08003140, 24, 'sdk_usart'),
    ('usart_word_length_set', 0x08003180, 24, 'sdk_usart'),
    ('usart_parity_config', 0x08003100, 24, 'sdk_usart'),
    ('usart_receive_config', 0x08003118, 16, 'sdk_usart'),
    ('usart_transmit_config', 0x08003158, 16, 'sdk_usart'),
    ('usart_hardware_flow_rts_config', 0x080030e8, 24, 'sdk_usart'),
    ('usart_hardware_flow_cts_config', 0x080030d0, 24, 'sdk_usart'),
    ('usart_transmit_fifo_threshold_config', 0x08003168, 24, 'sdk_usart'),
    ('usart_receive_fifo_threshold_config', 0x08003128, 24, 'sdk_usart'),
    ('usart_enable', 0x080030a8, 10, 'sdk_usart'),
    ('usart_deinit', 0x08002fe0, 198, 'sdk_usart'),
    ('usart_baudrate_set', 0x08002f10, 204, 'sdk_usart'),
]
CASE_UNITS = {name: unit for name, _, _, unit in CASES}
SYMBOLS = {name: address | 1 for name, address, _, _ in CASES}
# Library callees still owned by hand units or the runtime, under their SDK
# and AEABI names: the RCU reset helpers through their ITCM bridges, and
# microlib's memclr, whose 4-byte-aligned entry is the same routine.
SYMBOLS.update({'__aeabi_memclr4': 0x08000443})
# How each library unit reaches callees outside its own region: the ITCM
# units call the flash RCU helpers through the linker's ITCM bridges.
ITCM_RCU = {'rcu_periph_reset_enable': 0x5b31, 'rcu_periph_reset_disable': 0x5b3b}
UNIT_REFERENCES = {'sdk_timer': ITCM_RCU, 'sdk_adc': ITCM_RCU}
# Compiler-generated switch lookup tables inside these units. Whole-file
# compilation merges identical tables under the first function that needs
# one: the pulse-value writer shares the capture-value reader's table.
DATA_UNITS = {}
DATA_CASES = [('timer_channel_offsets', 0x5cb8, 80,
               '.rodata..Lswitch.table.timer_channel_capture_value_register_read'),
              # rcu_clock_freq_get's four identical local apbN_exp[] tables,
              # merged into one 8-byte mergeable constant.
              ('rcu_apb_prescaler_shifts', 0x08003524, 8, '.rodata.cst8')]
DATA_CASE_UNITS = {'timer_channel_offsets': 'sdk_timer',
                   'rcu_apb_prescaler_shifts': 'sdk_rcu'}
