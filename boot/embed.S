.section .rodata
.global app_start,app_end
app_start: .incbin "dist/demo.rv32"
app_end:
.section .note.GNU-stack,"",@progbits
