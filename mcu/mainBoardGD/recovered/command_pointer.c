/* The stock 32-bit MCU command pointer decoder is an identity conversion.
 * Kept in its actual separate translation unit so debug command calls remain.
 */
#include <stdint.h>
void *command_decode_ptr(uint32_t address) { return (void *)(uintptr_t)address; }
