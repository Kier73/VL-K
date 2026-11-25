#include "vlk.h"
#include <limits.h>
#define CAPACITY 64u
typedef struct { int32_t id; uint32_t kind,seed,a,b,state; uint64_t t; } Process;
static Process table[CAPACITY];
static uint32_t next_id=1, result, work;
uint32_t vk_abi(void) { return 1; }
uint32_t vk_value(void) { return result; }
uint32_t vk_work(void) { return work; }
static void clear(void) { result=0; work=0; }
static Process *lookup(int32_t id) {
    if(id<=0) return 0;
    for(uint32_t i=0;i<CAPACITY;i++) if(table[i].id==id) return &table[i];
    return 0;
}
static int32_t insert(Process p) {
    if(next_id>INT32_MAX) return VK_FULL;
    for(uint32_t i=0;i<CAPACITY;i++) if(!table[i].id) {
        p.id=(int32_t)next_id++; table[i]=p; return p.id;
    }
    return VK_FULL;
}
static int valid(uint32_t k) { return k==VK_AFFINE || k==VK_QUADRATIC; }
static int charge(uint32_t budget) { if(work==budget) return 0; ++work; return 1; }
static int32_t evaluate(Process p,uint64_t t,uint32_t budget,uint32_t *out) {
    if(t==UINT64_MAX) return VK_INVALID;
    uint32_t x=t>=p.t?p.state:p.seed;
    uint64_t n=t>=p.t?t-p.t:t;
    if(p.kind==VK_AFFINE) {
        uint32_t a=p.a,b=p.b;
        while(n) {
            if(n&1) { if(!charge(budget)) return VK_BUDGET; x=a*x+b; }
            n>>=1;
            if(n) { if(!charge(budget)) return VK_BUDGET; b=a*b+b; a=a*a; }
        }
    } else {
        if(n>budget) return VK_BUDGET;
        while(n--) { ++work; x=p.a*x*x+p.b; }
    }
    *out=x; return VK_OK;
}
int32_t vk_spawn(uint32_t kind,uint32_t seed,uint32_t a,uint32_t b) {
    clear(); if(!valid(kind)) return VK_INVALID;
    Process p={0,kind,seed,a,b,seed,0}; return insert(p);
}
int32_t vk_fork(int32_t id) {
    clear(); Process *p=lookup(id); return p?insert(*p):VK_INVALID;
}
int32_t vk_exit(int32_t id) {
    clear(); Process *p=lookup(id); if(!p) return VK_INVALID;
    p->id=0; return VK_OK;
}
uint64_t vk_time(int32_t id) { Process *p=lookup(id); return p?p->t:UINT64_MAX; }
int32_t vk_observe(int32_t id,uint64_t target,uint32_t budget) {
    clear(); Process *p=lookup(id); if(!p) return VK_INVALID;
    return evaluate(*p,target,budget,&result);
}
int32_t vk_advance(int32_t id,uint64_t expected,uint64_t target,uint32_t budget) {
    clear(); Process *p=lookup(id); if(!p) return VK_INVALID;
    if(p->t!=expected) return VK_CONFLICT;
    if(target<expected) return VK_INVALID;
    int32_t status=evaluate(*p,target,budget,&result);
    if(status==VK_OK) { p->state=result; p->t=target; }
    return status;
}
int32_t vk_restore(uint32_t kind,uint32_t seed,uint32_t a,uint32_t b,uint64_t t,uint32_t budget) {
    clear(); if(!valid(kind)) return VK_INVALID;
    Process p={0,kind,seed,a,b,seed,0};
    uint32_t x; int32_t status=evaluate(p,t,budget,&x);
    if(status!=VK_OK) return status;
    p.state=x; p.t=t; int32_t id=insert(p); if(id>0) result=x; return id;
}
