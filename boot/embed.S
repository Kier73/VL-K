.section .rodata
.global app_start,app_end
app_start: .incbin "dist/demo.rv32"
app_end:
.global file_start,file_end
file_start: .incbin "dist/file.rv32"
file_end:
.section .note.GNU-stack,"",@progbits
