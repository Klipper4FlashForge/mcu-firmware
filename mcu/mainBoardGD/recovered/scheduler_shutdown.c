/* Architecture-facing shutdown boundary; the runtime owns the jump context.
 * The architectural save/restore routines are separately reconstructed.
 * This path restores the saved context directly; it does not unwind a
 * language exception. Its noreturn+nothrow contract is shared by every
 * caller declaration, allowing the observed frameless try-shutdown call.
 */
#include <stdint.h>
extern void irq_disable(void);
extern uint64_t shutdown_jmp[20];
extern __attribute__((noreturn)) void longjmp(void *context, int value);

__attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason)
{
    irq_disable();
    longjmp(shutdown_jmp, reason);
}
