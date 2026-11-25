ENTRY(_start)
PHDRS { text PT_LOAD FILEHDR PHDRS FLAGS(5); data PT_LOAD FLAGS(6); }
SECTIONS {
 . = 0x10000 + SIZEOF_HEADERS;
 .text : { *(.text.start) *(.text*) *(.rodata*) } :text
 . = ALIGN(4096);
 .data : { *(.data*) *(.sdata*) } :data
 .bss : { *(.bss*) *(.sbss*) *(COMMON) } :data
 /DISCARD/ : { *(.comment*) *(.note*) *(.eh_frame*) }
}
