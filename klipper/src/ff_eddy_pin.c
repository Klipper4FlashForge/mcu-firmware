// FlashForge eddy oscillator enable-pin initialization.

#include "n32g45x.h" // GPIO_InitPeripheral

void
ff_eddy_pin_init(void)
{
    GPIO_InitType gpio;
    GPIO_InitStruct(&gpio);
    gpio.Pin = GPIO_PIN_1;
    gpio.GPIO_Mode = GPIO_MODE_OUT_PP;
    gpio.GPIO_Current = GPIO_DC_8MA;
    GPIO_InitPeripheral(NS_GPIOA, &gpio);
    GPIO_SetBits(NS_GPIOA, GPIO_PIN_1);
}
