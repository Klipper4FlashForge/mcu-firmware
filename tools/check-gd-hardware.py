#!/usr/bin/env python3
"""Gate the complete motor hardware initializer; SDK callees stay explicit.

2168 bytes are the full flash 1710..1f88 body, including both NOP delays.
There are no literal pools. This does not claim SDK or startup bootability.
"""
import json
from pathlib import Path
import sys

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from gd_function_gate import main, ROOT, load

UNITS = {'mclib_hardware': ('mclib_hardware.c', [])}
CASES = [('mclib_hardware_init', 0x08001710, 2168)]
CASE_UNITS = {'mclib_hardware_init': 'mclib_hardware'}
SYMBOLS = {
    'rcu_periph_clock_enable': 0x080028f1,
    'gpio_af_set': 0x080031d5,
    'gpio_mode_set': 0x080031df,
    'gpio_output_options_set': 0x080031e9,
    'mclib_pwm_init': 0x080031f3,
    'gd_motor_syscfg_route': 0x08002ed1,
    'timer_deinit': 0x080031fd,
    'timer_struct_para_init': 0x08003207,
    'timer_init': 0x08003211,
    'timer_channel_output_config': 0x0800321b,
    'timer_channel_output_mode_config': 0x08003225,
    'timer_channel_output_shadow_config': 0x0800322f,
    'timer_channel_output_pulse_value_config': 0x08003239,
    'timer_master_slave_mode_config': 0x08003243,
    'timer_master_output0_trigger_source_select': 0x0800324d,
    'timer_input_trigger_source_select': 0x08003257,
    'timer_slave_mode_select': 0x08003261,
    'adc_deinit': 0x0800326b,
    'adc_clock_config': 0x08003275,
    'adc_special_function_config': 0x0800327f,
    'adc_resolution_config': 0x08003289,
    'adc_data_alignment_config': 0x08003293,
    'adc_channel_length_config': 0x0800329d,
    'adc_regular_channel_config': 0x080032a7,
    'adc_external_trigger_config': 0x080032b1,
    'adc_dma_request_after_last_enable': 0x080032bb,
    'adc_dma_mode_enable': 0x080032c5,
    'adc_inserted_channel_config': 0x080032cf,
    'adc_interrupt_flag_clear': 0x080032d9,
    'adc_interrupt_enable': 0x080032e3,
    'adc_enable': 0x080032ed,
    'adc_calibration_mode_config': 0x080032f7,
    'adc_calibration_number': 0x08003301,
    'adc_calibration_enable': 0x0800330b,
    'dma_deinit': 0x08003315,
    'dma_single_data_mode_init': 0x0800331f,
    'dma_circulation_enable': 0x08003329,
    'dma_channel_enable': 0x08003333,
    'dma_flag_clear': 0x0800333d,
    'dma_interrupt_enable': 0x08003347,
    'nvic_priority_group_set': 0x08002079,
    'nvic_irq_enable': 0x08002011,
    'timer_enable': 0x08003351,
    'mclib_pwm_y': 0x2400884c, 'mclib_pwm_x': 0x24008858,
    'mclib_pwm_z': 0x24008864,
    'mclib_acquisition_y': 0x24003780, 'mclib_acquisition_x': 0x240037b0,
    'mclib_acquisition_z': 0x240037e0, 'mclib_acquisition_extruder': 0x24003750,
    'mclib_adc_dma_y': 0x24000000, 'mclib_adc_dma_z': 0x24000008,
}

def audit_calls(out):
    """Independent structural check, not a substitute for full-byte equality."""
    address, candidate = load('check-gd-motor.py').section(
        out / 'mclib_hardware_init.elf', '.text')
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()[0x1710:0x1f88]
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    def calls(blob, base):
        instructions = list(disassembler.disasm(blob, base))
        if sum(instruction.size for instruction in instructions) != len(blob):
            raise ValueError('hardware body did not decode completely')
        return [int(instruction.op_str.lstrip('#'), 0) for instruction in instructions
                if instruction.mnemonic == 'bl']

    expected, actual = calls(stock, 0x08001710), calls(candidate, address)
    report_path = out / 'results.json'
    report = json.loads(report_path.read_text())
    report['call_sequence_audit'] = dict(
        exact=expected == actual, expected_count=len(expected), actual_count=len(actual),
        expected_targets=expected, actual_targets=actual,
        limitation='Checks all direct call targets and order, not their argument values, SDK behavior or timing.')
    report['semantic_caveats'] = [
        'DMA parameter +24 (stock sp+40) is not initialized; ITCM2d34 consumes it to set/clear control bit8. No zero/default is invented.',
        'Stack layout differs; the value of that indeterminate DMA field cannot be claimed equal.',
        'Two ADC stabilization delays execute 6001 NOPs each; cycle timing is not proven equivalent.',
        'Register/stack store merging and scheduling differ; isolated source is not bootability evidence.',
    ]
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('Direct call sequence: %d/%d, %s (not argument/timing equivalence)' %
          (len(actual), len(expected), 'EXACT' if expected == actual else 'DIFF'))
    return expected == actual


if __name__ == '__main__':
    result = main('hardware', CASES, UNITS, CASE_UNITS, SYMBOLS)
    out = ROOT / 'work/mainBoardGD-hardware'
    for index, value in enumerate(sys.argv[1:], 1):
        if value == '--out':
            out = Path(sys.argv[index + 1]).resolve()
        elif value.startswith('--out='):
            out = Path(value.split('=', 1)[1]).resolve()
    calls_exact = audit_calls(out)
    raise SystemExit(result or not calls_exact)
