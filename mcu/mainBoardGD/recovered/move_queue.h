#ifndef MAINBOARDGD_MOVE_QUEUE_H
#define MAINBOARDGD_MOVE_QUEUE_H
#include <stdint.h>
struct move_node { struct move_node *next; };
struct move_queue_head { struct move_node *first, *last; };
void *move_alloc(void);
void move_free(void *node);
int move_queue_empty(struct move_queue_head *queue);
struct move_node *move_queue_first(struct move_queue_head *queue);
struct move_node *move_queue_pop(struct move_queue_head *queue);
int move_queue_push(struct move_node *node, struct move_queue_head *queue);
void move_queue_clear(struct move_queue_head *queue);
void move_queue_setup(struct move_queue_head *queue, int size);
void move_reset(void);
#endif
