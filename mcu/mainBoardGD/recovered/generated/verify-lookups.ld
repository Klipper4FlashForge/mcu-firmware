/* Isolated lookup comparison, not a bootable firmware link. */
SECTIONS {
  .encoder 0x21a0 : { *(.text.ctr_lookup_encoder) }
  .static_string 0x2420 : { *(.text.ctr_lookup_static_string) }
  .rodata 0x10000000 : { *(.rodata*) }
  .ARM.exidx : { *(.ARM.exidx*) }
}
/* Stock BL calls an ITCM veneer, not the flash strcmp directly. */
PROVIDE(strcmp = 0x00005b8b);
PROVIDE(command_encoder_50 = 0x00005d10);
PROVIDE(command_encoder_51 = 0x00005d18);
PROVIDE(command_encoder_52 = 0x00005d20);
PROVIDE(command_encoder_53 = 0x00005d28);
PROVIDE(generated_string_00006d10 = 0x00006d10);
PROVIDE(command_encoder_54 = 0x00005d30);
PROVIDE(command_encoder_55 = 0x00005d38);
PROVIDE(generated_string_00006c75 = 0x00006c75);
PROVIDE(command_encoder_0 = 0x00005d08);
PROVIDE(generated_string_00006b86 = 0x00006b86);
PROVIDE(command_encoder_56 = 0x00005d40);
PROVIDE(generated_string_00006cf1 = 0x00006cf1);
PROVIDE(command_encoder_57 = 0x00005d48);
PROVIDE(generated_string_00006cc5 = 0x00006cc5);
PROVIDE(command_encoder_58 = 0x00005d50);
PROVIDE(command_encoder_59 = 0x00005d58);
PROVIDE(generated_string_00006d75 = 0x00006d75);
PROVIDE(command_encoder_60 = 0x00005d60);
PROVIDE(generated_string_00006b4c = 0x00006b4c);
PROVIDE(command_encoder_61 = 0x00005d68);
PROVIDE(generated_string_00006cdd = 0x00006cdd);
PROVIDE(command_encoder_62 = 0x00005d70);
PROVIDE(generated_string_00006a7a = 0x00006a7a);
PROVIDE(command_encoder_63 = 0x00005d78);
PROVIDE(generated_string_000068f0 = 0x000068f0);
PROVIDE(command_encoder_64 = 0x00005d80);
PROVIDE(generated_string_00006c87 = 0x00006c87);
PROVIDE(command_encoder_65 = 0x00005d88);
PROVIDE(generated_string_00006d46 = 0x00006d46);
PROVIDE(command_encoder_66 = 0x00005d90);
PROVIDE(generated_string_00006b5a = 0x00006b5a);
PROVIDE(generated_string_00006c65 = 0x00006c65);
PROVIDE(generated_string_00006b0a = 0x00006b0a);
PROVIDE(generated_string_00006951 = 0x00006951);
PROVIDE(generated_string_0000697a = 0x0000697a);
PROVIDE(generated_string_0000699c = 0x0000699c);
PROVIDE(generated_string_00006968 = 0x00006968);
PROVIDE(generated_string_00006a29 = 0x00006a29);
PROVIDE(generated_string_00006dae = 0x00006dae);
PROVIDE(generated_string_0000693d = 0x0000693d);
PROVIDE(generated_string_0000692a = 0x0000692a);
PROVIDE(generated_string_000069ad = 0x000069ad);
PROVIDE(generated_string_00006ad5 = 0x00006ad5);
PROVIDE(generated_string_00006a43 = 0x00006a43);
PROVIDE(generated_string_00006bbd = 0x00006bbd);
PROVIDE(generated_string_000069dc = 0x000069dc);
PROVIDE(generated_string_00006b34 = 0x00006b34);
PROVIDE(generated_string_00006c4d = 0x00006c4d);
PROVIDE(generated_string_00006a01 = 0x00006a01);
PROVIDE(generated_string_0000698b = 0x0000698b);
PROVIDE(generated_string_00006c0e = 0x00006c0e);
PROVIDE(generated_string_00006be9 = 0x00006be9);
PROVIDE(generated_string_00006bac = 0x00006bac);
PROVIDE(generated_string_00006aad = 0x00006aad);
PROVIDE(generated_string_00006ac3 = 0x00006ac3);
PROVIDE(generated_string_00006c2f = 0x00006c2f);
PROVIDE(generated_string_00006a99 = 0x00006a99);
