#ifndef GD_MCLIB_HARDWARE_H
#define GD_MCLIB_HARDWARE_H

#include <stdint.h>
#include <stddef.h>
#include "mclib_state.h"
#include "gd32h7xx.h"


void mclib_hardware_init(void);
void mclib_pwm_init(struct mclib_pwm_state *);
void gd_motor_syscfg_route(uint32_t source, uint32_t destination);



extern volatile uint32_t mclib_adc_dma_y[2], mclib_adc_dma_z[2];
extern struct mclib_pwm_state mclib_pwm_y, mclib_pwm_x, mclib_pwm_z;
extern struct mclib_current_acquisition_state mclib_acquisition_y, mclib_acquisition_x;
extern struct mclib_current_acquisition_state mclib_acquisition_z, mclib_acquisition_extruder;

#endif
