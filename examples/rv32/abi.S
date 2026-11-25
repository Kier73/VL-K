.section .text.start,"ax"
.global _start
_start:
    # Unknown syscall must report ENOSYS.
    li a7,12345
    ecall
    li t0,-38
    bne a0,t0,fail
    # Invalid fd and invalid pointer must not touch host memory.
    li a7,64
    li a0,3
    li a1,0
    li a2,1
    ecall
    li t0,-9
    bne a0,t0,fail
    li a7,64
    li a0,1
    ecall
    li t0,-14
    bne a0,t0,fail
    # brk query, growth, store/load, shrink, repeat growth zeroes page.
    li a7,214
    li a0,0
    ecall
    mv s0,a0
    li t0,4096
    add s1,s0,t0
    mv a0,s1
    ecall
    bne a0,s1,fail
    li t0,0x87654321
    sw t0,0(s0)
    lw t1,0(s0)
    bne t0,t1,fail
    mv a0,s0
    ecall
    bne a0,s0,fail
    mv a0,s1
    ecall
    lw t0,0(s0)
    bnez t0,fail
    # M-extension corner cases, including divide by zero and overflow.
    li t0,0x80000000
    li t1,-1
    div t2,t0,t1
    bne t2,t0,fail
    rem t2,t0,t1
    bnez t2,fail
    divu t2,t0,zero
    bne t2,t1,fail
    remu t2,t0,zero
    bne t2,t0,fail
    mulh t2,t0,t1
    bnez t2,fail
    mulhsu t2,t0,t1
    li t3,0x80000000
    bne t2,t3,fail
    mulhu t2,t0,t1
    li t3,0x7fffffff
    bne t2,t3,fail
    li a0,23
    j done
fail:
    li a0,99
done:
    li a7,93
    ecall
