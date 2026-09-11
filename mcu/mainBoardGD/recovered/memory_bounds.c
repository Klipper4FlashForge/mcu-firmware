/* Static heap bounds observed in mainBoardGD's dynmem helpers. */
#include <stdint.h>
extern unsigned char dynamic_memory[0x5000];
void *dynmem_start(void) { return dynamic_memory; }
void *dynmem_end(void) { return dynamic_memory + sizeof(dynamic_memory); }
uint32_t timer_from_us(uint32_t usecs) { return usecs * 600u; }
