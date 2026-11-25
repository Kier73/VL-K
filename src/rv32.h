#ifndef VL_RV32_H
#define VL_RV32_H
#include <stdint.h>
#include <stddef.h>
#include "rvfs.h"
#define RV_SIZE (4u*1024u*1024u)
#define RV_PAGE 4096u
#define RV_STACK (RV_SIZE-65536u)
#define RV_R 1u
#define RV_W 2u
#define RV_X 4u
/* Guest addresses are offsets into caller-owned storage. No native guest pointers. */
typedef struct {
    uint32_t r[32], pc, heap, brk;
    uint8_t *mem;
    uint8_t pages[RV_SIZE/RV_PAGE];
    uint32_t steps, status;
    int halted;
} RV;
typedef int32_t (*rv_io)(void *, int, uint32_t, uint8_t *, uint32_t);
int rv_load(RV *, uint8_t *, const uint8_t *, size_t, int, const char *const *);
int rv_run(RV *, uint32_t, rv_io, void *, RVFS *);
#endif
