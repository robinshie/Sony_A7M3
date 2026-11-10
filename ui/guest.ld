ENTRY(_start)
PHDRS {
    code PT_LOAD FLAGS(5);
    data PT_LOAD FLAGS(6);
}
SECTIONS {
    . = 0x00100000;
    .text : { KEEP(*(.text.start)) *(.text*) } :code
    .rodata : { *(.rodata*) } :code
    . = ALIGN(4096);
    .data : { *(.data*) } :data
    . = ALIGN(8);
    .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .; } :data
}
