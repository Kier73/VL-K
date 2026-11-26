#include "rvproc.h"
static RPProcess *find(RPKernel *k,uint32_t pid){for(unsigned i=0;i<RP_SLOTS;i++)if(k->slots[i].result.state&&k->slots[i].result.pid==pid)return &k->slots[i];return 0;}
static void finish(RPKernel *k,RPProcess *p,uint32_t state,int trap){p->result.state=state;p->result.steps=p->vm.steps;p->result.status=p->vm.status;p->result.trap=trap;fs_drop_fds(k->fs,&p->fds);}
int rp_spawn(RPKernel *k,const uint8_t *image,size_t n,int argc,const char *const *argv,uint32_t limit,rv_io io,void *ctx,uint32_t *pid){
    if(!k->fs||!pid||!limit||k->last_pid==UINT32_MAX)return -1;
    unsigned i=0,free=0;while(i<RP_SLOTS&&k->slots[i].result.state)i++;
    if(i==RP_SLOTS)return -2;
    for(unsigned j=0;j<FS_OPEN;j++)if(!k->fs->opens[j].refs)free++;
    if(free<3)return -2;
    RPProcess *p=&k->slots[i];if(rv_load(&p->vm,p->ram,image,n,argc,argv))return -3;
    fs_reset_fds(k->fs,&p->fds);p->limit=limit;p->io=io;p->ctx=ctx;
    p->result=(RPResult){++k->last_pid,RP_READY,0,0,0};*pid=p->result.pid;return 0;
}
int rp_tick(RPKernel *k,uint32_t quantum){
    if(!quantum||!k->fs)return -1;
    for(unsigned i=0;i<RP_SLOTS;i++){
        unsigned j=(k->cursor+i)%RP_SLOTS;RPProcess *p=&k->slots[j];if(p->result.state!=RP_READY)continue;
        uint32_t left=p->limit-p->vm.steps,n=quantum<left?quantum:left;
        int r=rv_run(&p->vm,n,p->io,p->ctx,k->fs,&p->fds);k->cursor=(j+1)%RP_SLOTS;p->result.steps=p->vm.steps;
        if(r<0)finish(k,p,RP_TRAPPED,r);else if(!r)finish(k,p,RP_EXITED,0);else if(p->vm.steps==p->limit)finish(k,p,RP_LIMIT,0);
        return 1;
    }return 0;
}
int rp_observe(const RPKernel *k,uint32_t pid,RPResult *out){if(!out)return -1;for(unsigned i=0;i<RP_SLOTS;i++){const RPProcess *p=&k->slots[i];if(p->result.state&&p->result.pid==pid){*out=p->result;return 0;}}return -1;}
int rp_cancel(RPKernel *k,uint32_t pid){RPProcess *p=find(k,pid);if(!p||p->result.state!=RP_READY)return -1;finish(k,p,RP_CANCELLED,0);return 0;}
int rp_reap(RPKernel *k,uint32_t pid,RPResult *out){RPProcess *p=find(k,pid);if(!p||!out||p->result.state==RP_READY)return -1;*out=p->result;p->result.state=RP_FREE;p->io=0;p->ctx=0;return 0;}
