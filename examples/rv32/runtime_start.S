.section .text.start,"ax"
.global _start
_start:
    mv a0,sp
    call runtime
    li a7,93
    ecall
1:  j 1b
