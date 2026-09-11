/* Isolated lookup reconstruction for compiler configuration checks.
 * Local literals may be promoted by the compiler; shared strings and
 * encoders are external dependencies located by verify-lookups.ld. */
#include "generated.h"
extern const struct command_encoder command_encoder_50;
extern const struct command_encoder command_encoder_51;
extern const struct command_encoder command_encoder_52;
extern const struct command_encoder command_encoder_53;
extern const char generated_string_00006d10[];
extern const struct command_encoder command_encoder_54;
extern const struct command_encoder command_encoder_55;
extern const char generated_string_00006c75[];
extern const struct command_encoder command_encoder_0;
extern const char generated_string_00006b86[];
extern const struct command_encoder command_encoder_56;
extern const char generated_string_00006cf1[];
extern const struct command_encoder command_encoder_57;
extern const char generated_string_00006cc5[];
extern const struct command_encoder command_encoder_58;
extern const struct command_encoder command_encoder_59;
extern const char generated_string_00006d75[];
extern const struct command_encoder command_encoder_60;
extern const char generated_string_00006b4c[];
extern const struct command_encoder command_encoder_61;
extern const char generated_string_00006cdd[];
extern const struct command_encoder command_encoder_62;
extern const char generated_string_00006a7a[];
extern const struct command_encoder command_encoder_63;
extern const char generated_string_000068f0[];
extern const struct command_encoder command_encoder_64;
extern const char generated_string_00006c87[];
extern const struct command_encoder command_encoder_65;
extern const char generated_string_00006d46[];
extern const struct command_encoder command_encoder_66;
extern const char generated_string_00006b5a[];
extern const char generated_string_00006c65[];
extern const char generated_string_00006b0a[];
extern const char generated_string_00006951[];
extern const char generated_string_0000697a[];
extern const char generated_string_0000699c[];
extern const char generated_string_00006968[];
extern const char generated_string_00006a29[];
extern const char generated_string_00006dae[];
extern const char generated_string_0000693d[];
extern const char generated_string_0000692a[];
extern const char generated_string_000069ad[];
extern const char generated_string_00006ad5[];
extern const char generated_string_00006a43[];
extern const char generated_string_00006bbd[];
extern const char generated_string_000069dc[];
extern const char generated_string_00006b34[];
extern const char generated_string_00006c4d[];
extern const char generated_string_00006a01[];
extern const char generated_string_0000698b[];
extern const char generated_string_00006c0e[];
extern const char generated_string_00006be9[];
extern const char generated_string_00006bac[];
extern const char generated_string_00006aad[];
extern const char generated_string_00006ac3[];
extern const char generated_string_00006c2f[];
extern const char generated_string_00006a99[];

const struct command_encoder *
ctr_lookup_encoder(const char *str)
{
    if (__builtin_strcmp(str, "starting") == 0)
        return &command_encoder_50;
    if (__builtin_strcmp(str, "is_shutdown static_string_id=%hu") == 0)
        return &command_encoder_51;
    if (__builtin_strcmp(str, "shutdown clock=%u static_string_id=%hu") == 0)
        return &command_encoder_52;
    if (__builtin_strcmp(str, generated_string_00006d10) == 0)
        return &command_encoder_53;
    if (__builtin_strcmp(str, "mcu_version year=%u date=%u version=%u") == 0)
        return &command_encoder_54;
    if (__builtin_strcmp(str, generated_string_00006c75) == 0)
        return &command_encoder_55;
    if (__builtin_strcmp(str, generated_string_00006b86) == 0)
        return &command_encoder_0;
    if (__builtin_strcmp(str, generated_string_00006cf1) == 0)
        return &command_encoder_56;
    if (__builtin_strcmp(str, generated_string_00006cc5) == 0)
        return &command_encoder_57;
    if (__builtin_strcmp(str, "clock clock=%u") == 0)
        return &command_encoder_58;
    if (__builtin_strcmp(str, generated_string_00006d75) == 0)
        return &command_encoder_59;
    if (__builtin_strcmp(str, generated_string_00006b4c) == 0)
        return &command_encoder_60;
    if (__builtin_strcmp(str, generated_string_00006cdd) == 0)
        return &command_encoder_61;
    if (__builtin_strcmp(str, generated_string_00006a7a) == 0)
        return &command_encoder_62;
    if (__builtin_strcmp(str, generated_string_000068f0) == 0)
        return &command_encoder_63;
    if (__builtin_strcmp(str, generated_string_00006c87) == 0)
        return &command_encoder_64;
    if (__builtin_strcmp(str, generated_string_00006d46) == 0)
        return &command_encoder_65;
    if (__builtin_strcmp(str, generated_string_00006b5a) == 0)
        return &command_encoder_66;
    return NULL;
}

uint8_t
ctr_lookup_static_string(const char *str)
{
    if (__builtin_strcmp(str, "Shutdown cleared when not shutdown") == 0)
        return 2;
    if (__builtin_strcmp(str, "Timer too close") == 0)
        return 3;
    if (__builtin_strcmp(str, "sentinel timer called") == 0)
        return 4;
    if (__builtin_strcmp(str, "Invalid command") == 0)
        return 5;
    if (__builtin_strcmp(str, "Message encode error") == 0)
        return 6;
    if (__builtin_strcmp(str, "Command parser error") == 0)
        return 7;
    if (__builtin_strcmp(str, generated_string_00006c65) == 0)
        return 8;
    if (__builtin_strcmp(str, generated_string_00006b0a) == 0)
        return 9;
    if (__builtin_strcmp(str, generated_string_00006951) == 0)
        return 10;
    if (__builtin_strcmp(str, generated_string_0000697a) == 0)
        return 11;
    if (__builtin_strcmp(str, generated_string_0000699c) == 0)
        return 12;
    if (__builtin_strcmp(str, generated_string_00006968) == 0)
        return 13;
    if (__builtin_strcmp(str, generated_string_00006a29) == 0)
        return 14;
    if (__builtin_strcmp(str, generated_string_00006dae) == 0)
        return 15;
    if (__builtin_strcmp(str, generated_string_0000693d) == 0)
        return 16;
    if (__builtin_strcmp(str, generated_string_0000692a) == 0)
        return 17;
    if (__builtin_strcmp(str, generated_string_000069ad) == 0)
        return 18;
    if (__builtin_strcmp(str, generated_string_00006ad5) == 0)
        return 19;
    if (__builtin_strcmp(str, generated_string_00006a43) == 0)
        return 20;
    if (__builtin_strcmp(str, generated_string_00006bbd) == 0)
        return 21;
    if (__builtin_strcmp(str, generated_string_000069dc) == 0)
        return 22;
    if (__builtin_strcmp(str, generated_string_00006b34) == 0)
        return 23;
    if (__builtin_strcmp(str, generated_string_00006c4d) == 0)
        return 24;
    if (__builtin_strcmp(str, generated_string_00006a01) == 0)
        return 25;
    if (__builtin_strcmp(str, generated_string_0000698b) == 0)
        return 26;
    if (__builtin_strcmp(str, generated_string_00006c0e) == 0)
        return 27;
    if (__builtin_strcmp(str, generated_string_00006be9) == 0)
        return 28;
    if (__builtin_strcmp(str, generated_string_00006bac) == 0)
        return 29;
    if (__builtin_strcmp(str, generated_string_00006aad) == 0)
        return 30;
    if (__builtin_strcmp(str, generated_string_00006ac3) == 0)
        return 31;
    if (__builtin_strcmp(str, generated_string_00006c2f) == 0)
        return 32;
    if (__builtin_strcmp(str, generated_string_00006a99) == 0)
        return 33;
    return 255;
}
