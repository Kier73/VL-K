#ifndef VL_RVPROC_H
#define VL_RVPROC_H
#include "rv32.h"
#ifndef RP_SLOTS
#define RP_SLOTS 2u
#endif
#define RP_IMAGES 4u
typedef struct {const char *name;const uint8_t *bytes;size_t size;} RPImage;
enum { RP_FREE, RP_READY, RP_EXITED, RP_TRAPPED, RP_LIMIT, RP_CANCELLED, RP_BLOCKED };
typedef struct {uint32_t pid,state,steps,status;int trap;} RPResult;
typedef struct {RPResult result;uint32_t limit,parent;RV vm;RVFds fds;rv_io io;void *ctx;
#ifndef RV_OBJECT_BACKEND
uint8_t ram[RV_SIZE];
#endif
} RPProcess;
/* Zero-initialize once, then bind fs. Single-owner kernel; callbacks must not reenter. */
typedef struct {RVFS *fs;uint32_t last_pid,cursor,blocks,wakes,forks,shared_pages;RPImage images[RP_IMAGES];
#ifdef RV_OBJECT_BACKEND
ROPool pool;uint8_t scratch[RV_SIZE];
#endif
RPProcess slots[RP_SLOTS];} RPKernel;
int rp_register(RPKernel *,const char *,const uint8_t *,size_t);
int rp_spawn(RPKernel *,const uint8_t *,size_t,int,const char *const *,uint32_t,rv_io,void *,uint32_t *);
int rp_connect(RPKernel *,uint32_t,uint32_t);
int rp_tick(RPKernel *,uint32_t);
int rp_observe(const RPKernel *,uint32_t,RPResult *);
int rp_cancel(RPKernel *,uint32_t);
int rp_reap(RPKernel *,uint32_t,RPResult *);
#endif
