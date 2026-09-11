# GD32H7xx standard peripheral library, V1.1.0 (2023-06-21)

GigaDevice's firmware library as shipped, BSD-3-Clause (see each file's
header). `Include/` is the complete peripheral header set plus the device
header, `system_gd32h7xx.h`, `gd32h7xx_libopt.h` and CMSIS 5.7.0's
`cmsis_armclang.h`; `Source/` holds only the peripheral files the stock image
links: timer, adc, dma, rcu, gpio, usart, misc, syscfg.

Compiled as whole files with Arm Compiler 6.20 at `-O1`, these reproduce the
stock SDK bodies byte for byte where the hand reconstructions in `../..`
never did (`timer_init`, `timer_input_trigger_source_select`,
`nvic_irq_enable`, `mpu_region_config`, ...); the hand versions are retired
function by function as each real one is confirmed. The source was fetched
from a public copy (github.com/vanvught/GD32H759I-EVAL-board-DMX512-RDM,
`lib-gd32/gd32h7xx/`); the version string is in every file.
