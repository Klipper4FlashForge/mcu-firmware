/* OID allocation from Klipper basecmd.c, Kevin O'Connor, GPLv3.
 * Stock inlines allocation into the OID bodies. The shared error string is
 * an actual generated data object, not another local string-pool copy.
 */
#include <stdint.h>
#include "generated/generated.h"
struct oid_s { void *type, *data; };
extern struct oid_s *oids;
extern uint8_t oid_count;
extern uint16_t move_count;
extern void *alloc_end;
extern void *dynmem_end(void);
extern const char generated_string_0000692a[];
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);

static void *alloc_chunk(uint32_t size)
{
    if ((uint8_t *)alloc_end + size > (uint8_t *)dynmem_end())
        sched_shutdown(ctr_lookup_static_string(generated_string_0000692a));
    void *data = alloc_end;
    alloc_end = (uint8_t *)alloc_end + ((size + 3u) & ~3u);
    __builtin_memset(data, 0, size);
    return data;
}

void command_allocate_oids(uint32_t *args)
{
    if (oids)
        sched_shutdown(ctr_lookup_static_string("oids already allocated"));
    uint8_t count = args[0];
    oids = alloc_chunk(sizeof(*oids) * count);
    oid_count = count;
}

void *oid_alloc(uint8_t oid, void *type, uint16_t size)
{
    /* Operand order retains stock CMP count, oid / BLS at 0x3f3e.
     * The common compiler profile matches this entire 164-byte function.
     */
    if (oid_count <= oid || oids[oid].type || move_count)
        sched_shutdown(ctr_lookup_static_string("Can't assign oid"));
    oids[oid].type = type;
    void *data = alloc_chunk(size);
    oids[oid].data = data;
    return data;
}

void *oid_lookup(uint8_t oid, void *type)
{
    /* Stock saves LR on entry. The globally tested no-shrink-wrap profile
     * reproduces that prologue without a local attribute or artificial work.
     */
    if (oid_count <= oid || oids[oid].type != type)
        sched_shutdown(ctr_lookup_static_string("Invalid oid type"));
    return oids[oid].data;
}

void *oid_next(uint8_t *i, void *type)
{
    uint8_t oid = *i;
    for (;;) {
        oid++;
        if (oid >= oid_count)
            return NULL;
        struct oid_s *o = &oids[oid];
        if (o->type == type) {
            *i = oid;
            return o->data;
        }
    }
}
