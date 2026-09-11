#ifndef GD_RUNTIME_MEMORY_H
#define GD_RUNTIME_MEMORY_H

#include <stddef.h>

/* AEABI helpers return no value; memset's count/value order differs from C.
 * Copy and move veneers share the overlap-safe flash body at 080003f4.
 * Neither alias promises the original destination in r0 on return. */
void __aeabi_memmove(void *destination, const void *source, size_t count);
void __aeabi_memcpy(void *destination, const void *source, size_t count);
void __aeabi_memset(void *destination, size_t count, int value);
void __aeabi_memclr(void *destination, size_t count);
void *memset(void *destination, int value, size_t count);
int strcmp(const char *left, const char *right);
void *memchr(const void *source, int value, size_t count);

#endif
