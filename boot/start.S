.section .multiboot,"a"
.align 4
.long 0x1badb002, 0, -(0x1badb002)
.section .text
.global _start
_start:
    cli
    cld
    mov $stack_top, %esp
    sub $12, %esp
    push %eax
    call kmain
1:  hlt
    jmp 1b
.section .bss
.align 16
stack: .skip 65536
stack_top:
.section .note.GNU-stack,"",@progbits
