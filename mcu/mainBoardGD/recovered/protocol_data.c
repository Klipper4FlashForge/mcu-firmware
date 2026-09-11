/* Protocol records retained outside generated compile_time_request output.
 * The ACK encoder has no parameters; five is the empty frame's total size.
 * The parser-error literal is the separate ITCM-tail copy, not the identical
 * text in the generated lookup's local pool at 0x27ac.
 */
#include "command_protocol.h"

const struct command_encoder encode_acknak = {
    .encoded_msgid = 0, .max_size = 5, .num_params = 0, .param_types = 0
};
const char generated_string_00006dc2[] = "Command parser error";
