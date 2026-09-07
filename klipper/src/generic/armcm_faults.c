// ARM Cortex-M fault handler stubs
//
// Copyright (C) 2024  FlashForge
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

// The PendSV slot points at DefaultHandler; the other unused system
// exception slots stay null.
void DefaultHandler(void);
DECL_ARMCM_IRQ(DefaultHandler, -2);
