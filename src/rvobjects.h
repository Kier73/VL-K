#ifndef VL_RVOBJECTS_H
#define VL_RVOBJECTS_H
#include <stdint.h>
#define RO_PAGE 4096u
#define RO_VPAGES 1024u
#define RO_OBJECTS 512u
#define RO_PERIOD 16u
/* Object zero is an implicit all-zero page. Nonzero handles are pool-local. */
typedef struct {uint16_t refs,dense;uint8_t period,pattern[RO_PERIOD];} ROObject;
typedef struct {ROObject objects[RO_OBJECTS];uint8_t used[RO_OBJECTS];uint8_t data[RO_OBJECTS][RO_PAGE];uint32_t reserved,live,dense,peak_dense,copies;} ROPool;
typedef struct {uint16_t id[RO_VPAGES];uint8_t mapped[RO_VPAGES];} ROSpace;
int ro_map(ROPool *,ROSpace *,unsigned,unsigned);
int ro_unmap(ROPool *,ROSpace *,unsigned,unsigned);
int ro_fork(ROPool *,ROSpace *,const ROSpace *);
void ro_drop(ROPool *,ROSpace *);
int ro_read(const ROPool *,const ROSpace *,uint32_t,uint8_t *,uint32_t);
int ro_write(ROPool *,ROSpace *,uint32_t,const uint8_t *,uint32_t);
#endif
