/* ITCM 0x38b0: MPU setup, architectural cache invalidation, then scheduler.
 * CMSIS supplies the observed barriers and cache set/way loops. The MPU
 * helper calls remain out of line, matching the vendor API boundaries.
 */
#include <stdint.h>
/* The SDK device header brings CMSIS core_cm7.h; under an open clang the
 * barrier macros there are GCC inline assembly, spelled as intrinsics here. */
#include "gd32h7xx.h"
#ifndef __ARMCC_VERSION
#undef __DSB
#undef __DMB
#undef __ISB
#define __DSB() __builtin_arm_dsb(15)
#define __DMB() __builtin_arm_dmb(15)
#define __ISB() __builtin_arm_isb(15)
#endif

void gd_jscope_init(void);
/* Stock keeps a return path at this call site; do not add noreturn here. */
void sched_main(void);

int gd_board_main(void)
{
    mpu_region_init_struct region;
    mpu_region_struct_para_init(&region);
    ARM_MPU_Disable();
    MPU->RBAR = 0;
    MPU->RASR = 0;

    region.region_base_address = 0;
    region.region_number = 0;
    region.region_size = 31;
    region.subregion_disable = 0x87;
    region.tex_type = 0;
    region.access_permission = 0;
    region.access_shareable = 0;
    region.access_cacheable = 0;
    region.access_bufferable = 0;
    region.instruction_exec = 1;
    mpu_region_config(&region);
    mpu_region_enable();

    region.region_base_address = 0x24000000;
    region.region_number = 1;
    region.region_size = 8;
    region.subregion_disable = 0;
    region.tex_type = 0;
    region.access_permission = 3;
    region.access_shareable = 1;
    region.access_cacheable = 1;
    region.access_bufferable = 0;
    region.instruction_exec = 0;
    mpu_region_config(&region);
    mpu_region_enable();

    ARM_MPU_Enable(MPU_CTRL_PRIVDEFENA_Msk);
    SCB_EnableICache();
    SCB_EnableDCache();
    gd_jscope_init();
    sched_main();
    return 0;
}
