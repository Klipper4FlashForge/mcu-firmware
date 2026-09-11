/* Klipper basecmd.c allocation/finalization (GPLv3, Kevin O'Connor).
 * mainBoardGD inlines both allocation helpers and move_reset into this
 * command. Retain the second end-of-memory check, zero fill, rounded bump
 * pointer and the distinct free-list tail reloads visible in stock.
 */
#include <stdint.h>
#include "move_queue.h"
#include "generated/generated.h"

extern void *alloc_end, *move_list;
extern struct move_node *move_free_list;
extern uint16_t move_count;
extern uint8_t move_item_size;
extern uint32_t config_crc;
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

static void *alloc_chunks(uint32_t size, uint32_t count, uint16_t *avail)
{
    uint32_t can_alloc = 0;
    uint8_t *position = alloc_end, *end = dynmem_end();
    while (can_alloc < count && position + size <= end) {
        can_alloc++;
        position += size;
    }
    if (!can_alloc)
        sched_shutdown(ctr_lookup_static_string("alloc_chunks failed"));
    void *data = alloc_chunk(position - (uint8_t *)alloc_end);
    *avail = can_alloc;
    return data;
}

static void reset_moves(void)
{
    uint16_t count = move_count;
    if (!count)
        return;
    uint8_t *position = move_list;
    uint8_t stride = move_item_size;
    for (uint32_t i = 0; i < count - 1; i++) {
        struct move_node *node = (void *)position;
        position += stride;
        node->next = (void *)position;
    }
    void *base = move_list;
    struct move_node *node = (void *)((uint8_t *)base + (count - 1) * move_item_size);
    node->next = 0;
    move_free_list = base;
}

void command_finalize_config(uint32_t *args)
{
    if (move_count)
        sched_shutdown(ctr_lookup_static_string("Already finalized"));
    if (move_item_size < sizeof(struct move_node))
        move_item_size = sizeof(struct move_node);
    move_list = alloc_chunks(move_item_size, 1024, &move_count);
    reset_moves();
    config_crc = args[0];
}
