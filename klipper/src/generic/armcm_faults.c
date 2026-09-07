// ARM Cortex-M fault handler stubs
//
// Copyright (C) 2019  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <stdint.h> // uint32_t
#include "armcm_boot.h" // DECL_ARMCM_IRQ

// FlashForge fills three fault vectors that Klipper leaves on DefaultHandler.
void
NMIHandler(void)
{
}
DECL_ARMCM_IRQ(NMIHandler, -14);

void
HardFaultHandler(void)
{
    for (;;)
        ;
}
DECL_ARMCM_IRQ(HardFaultHandler, -13);

void
SVCallHandler(void)
{
}
DECL_ARMCM_IRQ(SVCallHandler, -5);

// The PendSV slot points at DefaultHandler while the other unused system
// exception slots stay null (stock has 0x08008921 at offset 0x38).
void DefaultHandler(void);
DECL_ARMCM_IRQ(DefaultHandler, -2);
