#ifndef VL_BOOT_MODULE_H
#define VL_BOOT_MODULE_H
#include <stdint.h>
/* Multiboot v1, one optional ELF module; bootloader-provided flat physical addresses. */
static inline int mb_range(uint32_t a,uint32_t n,uint32_t top){return a>=4096u&&a<=top&&n<=top-a;}
static inline uint32_t mb_top(uint32_t upper_kib){return upper_kib<=0x3ffbffu?0x100000u+upper_kib*1024u:0;}
static inline int mb_module(uint32_t start,uint32_t end,uint32_t top,uint32_t kernel_end,uint32_t max_size){return start>=kernel_end&&end>start&&end-start<=max_size&&mb_range(start,end-start,top);}
#endif
