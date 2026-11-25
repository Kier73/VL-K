.section .text.start,"ax"
.global _start
_start:
    lw a0,0(sp)
    addi a1,sp,4
    call main
    li a7,93
    ecall
1:  j 1b
