/* Move storage and FIFO operations from Klipper basecmd.c (GPLv3).
 * Shutdown reset walks fixed-size allocations; queue operations themselves
 * do not invent locking beyond the observed move_alloc IRQ critical section.
 */
#include "move_queue.h"
#include "generated/generated.h"

extern struct move_node *move_free_list;
extern void *move_list;
extern uint16_t move_count;
extern uint8_t move_item_size;
extern uint32_t irq_save(void);
extern void irq_restore(uint32_t flags);
extern __attribute__((noreturn, nothrow)) void sched_shutdown(uint_fast8_t reason);

void *move_alloc(void)
{
    uint32_t flags = irq_save();
    struct move_node *node = move_free_list;
    if (!node)
        sched_shutdown(ctr_lookup_static_string("Move queue overflow"));
    move_free_list = node->next;
    irq_restore(flags);
    return node;
}

void move_free(void *storage)
{
    struct move_node *node = storage;
    node->next = move_free_list;
    move_free_list = node;
}

void move_queue_clear(struct move_queue_head *queue) { queue->first = 0; }
int move_queue_empty(struct move_queue_head *queue) { return queue->first == 0; }
struct move_node *move_queue_first(struct move_queue_head *queue) { return queue->first; }

struct move_node *move_queue_pop(struct move_queue_head *queue)
{
    struct move_node *node = queue->first;
    queue->first = node->next;
    return node;
}

int move_queue_push(struct move_node *node, struct move_queue_head *queue)
{
    struct move_node *first = queue->first;
    node->next = 0;
    /* Stock snapshots first before clearing the new node (0x3e5a/0x3e64),
     * then selects two pointer destinations for the shared 0x3e78/0x3e7a
     * store tail. Link the previous node before publishing the new last;
     * an empty queue publishes last before first. */
    struct move_node **previous, **publish;
    int was_empty;
    if (first) {
        previous = &queue->last->next;
        publish = &queue->last;
        was_empty = 0;
    } else {
        previous = &queue->last;
        publish = &queue->first;
        was_empty = 1;
    }
    *previous = node;
    *publish = node;
    return was_empty;
}

void move_queue_setup(struct move_queue_head *queue, int size)
{
    queue->first = queue->last = 0;
    if (size > 255 || move_count)
        sched_shutdown(ctr_lookup_static_string("Invalid move request size"));
    if (move_item_size < size)
        move_item_size = size;
}

void move_reset(void)
{
    uint16_t count = move_count;
    if (!count)
        return;
    /* Stock snapshots the list base/stride for the loop, then reloads them
     * for the tail link. Keeping that distinction avoids alias-driven loads
     * introduced by these externally named reconstructed globals.
     */
    uint8_t *position = move_list;
    uint8_t stride = move_item_size;
    /* Widen only the subtraction's constant: after the zero-count return,
     * count - 1 is 0..65534 and its byte-stride product is at most
     * 16711170. This preserves the full input domain and the tail reloads;
     * it is a matching-C spelling, not a recovered original type claim. */
    for (uint32_t i = 0; i < count - INT64_C(1); i++) {
        struct move_node *node = (void *)position;
        position += stride;
        node->next = (void *)position;
    }
    void *base = move_list;
    struct move_node *node = (void *)((uint8_t *)base
                                     + (count - INT64_C(1)) * move_item_size);
    node->next = 0;
    move_free_list = base;
}
