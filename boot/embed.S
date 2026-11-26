.section .rodata
.global app_start,app_end
app_start: .incbin "dist/demo.rv32"
app_end:
.global file_start,file_end
file_start: .incbin "dist/file.rv32"
file_end:
.global shell_start,shell_end,filter_start,filter_end
shell_start: .incbin "dist/shell.rv32"
shell_end:
filter_start: .incbin "dist/filter.rv32"
filter_end:
.section .note.GNU-stack,"",@progbits
