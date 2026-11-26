#ifndef VL_RV32_H
#define VL_RV32_H
#include <stdint.h>
#include <stddef.h>
#include "rvfs.h"
#ifdef RV_OBJECT_BACKEND
#include "rvobjects.h"
#endif
#define RV_SIZE (4u*1024u*1024u)
#define RV_PAGE 4096u
#define RV_STACK (RV_SIZE-65536u)
#define RV_R 1u
#define RV_W 2u
#define RV_X 4u
#define RV_MAP 8u /* anonymous mapping, including PROT_NONE */
/* Guest addresses are offsets into caller-owned storage. No native guest pointers. */
typedef struct RV {
    uint32_t r[32], pc, heap, brk;
    uint8_t *mem;
    uint8_t pages[RV_SIZE/RV_PAGE];
    uint32_t steps, status;
    int halted, process_calls;
    struct RV *peer;
    uint8_t borrowed[RV_SIZE/RV_PAGE];
    uint32_t cow_copies;
#ifdef RV_OBJECT_BACKEND
    ROPool *pool;
    ROSpace space;
#endif
} RV;
typedef int32_t (*rv_io)(void *, int, uint32_t, uint8_t *, uint32_t);
int rv_load(RV *, uint8_t *, const uint8_t *, size_t, int, const char *const *);
int rv_load_env(RV *, uint8_t *, const uint8_t *, size_t, int, const char *const *, int, const char *const *);
/* Trusted memory helpers; caller validates the guest range and permissions. */
uint32_t rv_word(RV *,uint32_t,unsigned);
uint8_t *rv_buffer(RV *,uint32_t,uint32_t,int);
unsigned rv_fork_memory(RV *,uint8_t *,RV *);
void rv_release_memory(RV *);
int rv_replace_env(RV *,const uint8_t *,size_t,int,const char *const *,int,const char *const *);
void rv_read_bytes(RV *,uint32_t,uint8_t *,uint32_t);
void rv_write_bytes(RV *,uint32_t,const uint8_t *,uint32_t);
#ifdef RV_OBJECT_BACKEND
int rv_load_pool(RV *,ROPool *,uint8_t *,const uint8_t *,size_t,int,const char *const *,int,const char *const *);
#endif
int rv_check(RV *,uint32_t,uint32_t,unsigned);
int rv_run(RV *, uint32_t, rv_io, void *, RVFS *, RVFds *);
#endif
