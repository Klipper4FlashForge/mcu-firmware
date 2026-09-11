/* Reconstructed generated-layer ABI. ARM32 sizes are verified at compile time.
 * Parameter enum and structures follow klipper/src/command.h. */
#ifndef MAINBOARDGD_GENERATED_H
#define MAINBOARDGD_GENERATED_H
#include <stddef.h>
#include <stdint.h>

enum {
    PT_uint32, PT_int32, PT_uint16, PT_int16, PT_byte,
    PT_string, PT_progmem_buffer, PT_buffer,
};
struct command_encoder {
    uint16_t encoded_msgid;
    uint8_t max_size, num_params;
    const uint8_t *param_types;
};
struct command_parser {
    uint16_t encoded_msgid;
    uint8_t num_args, flags, num_params;
    const uint8_t *param_types;
    void (*func)(uint32_t *args);
};
_Static_assert(sizeof(void *) == 4, "ARM32 pointers required");
_Static_assert(sizeof(struct command_encoder) == 8, "encoder ABI");
_Static_assert(offsetof(struct command_encoder, param_types) == 4, "encoder pointer ABI");
_Static_assert(sizeof(struct command_parser) == 16, "parser ABI");
_Static_assert(offsetof(struct command_parser, param_types) == 8, "parser pointer ABI");
_Static_assert(offsetof(struct command_parser, func) == 12, "handler pointer ABI");

extern const struct command_parser command_index[];
extern const uint16_t command_index_size;
extern const uint8_t command_identify_data[];
extern const uint32_t command_identify_size;
const struct command_encoder *ctr_lookup_encoder(const char *str);
uint8_t ctr_lookup_static_string(const char *str);
void ctr_run_initfuncs(void);
void ctr_run_shutdownfuncs(void);
void ctr_run_taskfuncs(void);
#endif
