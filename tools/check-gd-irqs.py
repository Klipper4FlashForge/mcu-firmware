#!/usr/bin/env python3
"""Motor sample IRQs, actual fault traps and SysTick C source profile."""
from gd_function_gate import main

UNITS = {'motor_irqs': ('motor_irqs.c', []), 'timer_dispatch': ('timer_dispatch.c', []),
         'timer_task': ('timer_dispatch.c', ['GD_TIMER_TASK'])}
CASES = [('gd_motor_adc_irq', 0, 120), ('BusFault_Handler', 0x78, 2),
         ('gd_motor_dma0_irq', 0x80, 70), ('gd_motor_dma1_irq', 0xc8, 70),
         ('DebugMon_Handler', 0x110, 2), ('HardFault_Handler', 0x118, 2),
         ('MemManage_Handler', 0x120, 2), ('NMI_Handler', 0x128, 2),
         ('PendSV_Handler', 0x130, 2), ('SVC_Handler', 0x138, 2),
         ('SysTick_Handler', 0x140, 220), ('UsageFault_Handler', 0x280, 2),
         ('timer_task', 0x5868, 44)]
CASE_UNITS = {name: 'timer_task' if name == 'timer_task' else
              'timer_dispatch' if name == 'SysTick_Handler'
              else 'motor_irqs' for name, _, _ in CASES}
SYMBOLS = {'adc_interrupt_flag_get': 0x4e1, 'adc_interrupt_flag_clear': 0x4d9,
           'dma_interrupt_flag_get': 0x2b61, 'dma_interrupt_flag_clear': 0x2b29,
           'mclib_current_acquisition_calibrate': 0x3a19,
           'mclib_control_loop_a': 0x5b1d, 'mclib_control_loop_b': 0x5b27,
           'mclib_motor_x': 0x2400282c, 'mclib_motor_y': 0x24002514,
           'mclib_motor_z': 0x24002b44, 'mclib_motor_extruder': 0x240021ec,
           'sched_timer_dispatch': 0x4441, 'sched_tasks_busy': 0x4429,
           'ctr_lookup_static_string': 0x2421, 'sched_try_shutdown': 0x44d9,
           'irq_disable': 0x3881, 'irq_enable': 0x3889,
           'timer_repeat_until': 0x24008ab0}

if __name__ == '__main__':
    raise SystemExit(main('irqs', CASES, UNITS, CASE_UNITS, SYMBOLS))
