#include "rvproc.h"
static RPProcess *find(RPKernel *k,uint32_t pid){for(unsigned i=0;i<RP_SLOTS;i++)if(k->slots[i].result.state&&k->slots[i].result.pid==pid)return &k->slots[i];return 0;}
static void finish(RPKernel *k,RPProcess *p,uint32_t state,int trap){p->result.state=state;p->result.steps=p->vm.steps;p->result.status=p->vm.status;p->result.trap=trap;fs_drop_fds(k->fs,&p->fds);rv_release_memory(&p->vm);for(unsigned i=0;i<RP_SLOTS;i++)if(k->slots[i].parent==p->result.pid)k->slots[i].parent=0;}
int rp_spawn(RPKernel *k,const uint8_t *image,size_t n,int argc,const char *const *argv,uint32_t limit,rv_io io,void *ctx,uint32_t *pid){
    if(!k->fs||!pid||!limit||k->last_pid==0x7fffffffu)return -1;
    unsigned i=0,free=0;while(i<RP_SLOTS&&k->slots[i].result.state)i++;
    if(i==RP_SLOTS)return -2;
    for(unsigned j=0;j<FS_OPEN;j++)if(!k->fs->opens[j].refs)free++;
    if(free<3)return -2;
    RPProcess *p=&k->slots[i];if(rv_load(&p->vm,p->ram,image,n,argc,argv))return -3;
    fs_reset_fds(k->fs,&p->fds);p->vm.process_calls=1;p->parent=0;p->limit=limit;p->io=io;p->ctx=ctx;
    p->result=(RPResult){++k->last_pid,RP_READY,0,0,0};*pid=p->result.pid;return 0;
}
/* Link producer stdout to consumer stdin before either runs. Reserve temporary slots
 * before replacing stdio, so failed connection leaves both tables unchanged. */
int rp_connect(RPKernel *k,uint32_t producer,uint32_t consumer){
    RPProcess *a=find(k,producer),*b=find(k,consumer);if(!a||!b||a==b||a->result.state!=RP_READY||b->result.state!=RP_READY||a->vm.steps||b->vm.steps)return -1;
    if(a->fds.slots[3]||b->fds.slots[3])return -1;
    int r=fs_pipe(k->fs,&b->fds,&a->fds,3,3);if(r)return r;
    fs_dup(k->fs,&a->fds,3,1,0,1);fs_dup(k->fs,&b->fds,3,0,0,1);fs_close(k->fs,&a->fds,3);fs_close(k->fs,&b->fds,3);return 0;
}
static int same(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
int rp_register(RPKernel *k,const char *name,const uint8_t *bytes,size_t size){
    if(!name||!fs_name(name)||!bytes||!size||size>RV_SIZE)return -1;
    unsigned i=0;for(;i<RP_IMAGES&&k->images[i].name;i++)if(same(name,k->images[i].name))return -1;
    if(i==RP_IMAGES)return -1;
    k->images[i]=(RPImage){name,bytes,size};return 0;
}
static int live(const RPProcess *p){return p->result.state==RP_READY||p->result.state==RP_BLOCKED;}
static void write32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static int string(RV *v,uint32_t addr,char *out,unsigned cap){for(unsigned i=0;i<cap;i++){if(!rv_check(v,addr,1,RV_R))return -14;out[i]=(char)rv_word(v,addr++,1);if(!out[i])return 0;}return -7;}
static int vector(RV *v,uint32_t addr,char buf[16][256],const char **out,int *count){
    *count=0;if(!addr)return 0;
    for(unsigned i=0;i<=16;i++){if(!rv_check(v,addr,4,RV_R))return -14;uint32_t p=rv_word(v,addr,4);if(!p)return 0;if(i==16)return -7;int r=string(v,p,buf[i],256);if(r)return r;out[i]=buf[i];(*count)++;addr+=4;}return -7;
}
/* Only the direct child's terminal state can satisfy a wait. */
static RPProcess *child(RPKernel *k,RPProcess *p,uint32_t pid,int *exists){
    *exists=0;for(unsigned i=0;i<RP_SLOTS;i++){RPProcess *q=&k->slots[i];if(!q->result.state||q->parent!=p->result.pid||(pid!=UINT32_MAX&&pid!=q->result.pid))continue;*exists=1;if(!live(q))return q;}return 0;
}
static int waiting_ready(RPKernel *k,RPProcess *p){int exists;return child(k,p,p->vm.r[10],&exists)!=0||!exists;}
static int32_t process_call(RPKernel *k,RPProcess *p,int *replaced){
    RV *v=&p->vm;uint32_t a=v->r[10],b=v->r[11],c=v->r[12];*replaced=0;
    switch(v->r[17]){
    case 172:return (int32_t)p->result.pid;
    case 59:{if(b&~02000000u)return -22;if(!rv_check(v,a,8,RV_W))return -14;unsigned x=0,y;while(x<FS_FDS&&p->fds.slots[x])x++;for(y=x+1;y<FS_FDS&&p->fds.slots[y];y++){}if(y>=FS_FDS)return -24;int r=fs_pipe(k->fs,&p->fds,&p->fds,x,y);if(r)return r;p->fds.cloexec[x]=p->fds.cloexec[y]=(uint8_t)!!b;uint8_t *out=rv_buffer(v,a,8,1);write32(out,x);write32(out+4,y);return 0;}
    case 220:{/* Linux clone's fork-like subset: SIGCHLD, original stack, no extra pointers. */
        if(a!=17||b||c||v->r[13]||v->r[14])return -22;
        if(k->last_pid==0x7fffffffu||v->steps+1>=p->limit)return -11;
        unsigned i=0;while(i<RP_SLOTS&&k->slots[i].result.state)i++;if(i==RP_SLOTS)return -11;
        RPProcess *q=&k->slots[i];if(v->peer)return -11;unsigned shared=rv_fork_memory(&q->vm,q->ram,v);k->forks++;k->shared_pages+=shared;q->vm.r[10]=0;q->vm.pc+=4;q->vm.steps=0;
        q->fds=p->fds;for(unsigned j=0;j<FS_FDS;j++)if(q->fds.slots[j])k->fs->opens[q->fds.slots[j]-1].refs++;
        q->parent=p->result.pid;q->limit=p->limit-v->steps-1;q->io=p->io;q->ctx=p->ctx;q->result=(RPResult){++k->last_pid,RP_READY,0,0,0};return (int32_t)q->result.pid;}
    case 221:{char name[FS_NAME],args[16][256],env[16][256];const char *argv[16],*envp[16];int argc,envc;int r=string(v,a,name,sizeof(name));if(r)return r;
        const RPImage *image=0;for(unsigned i=0;i<RP_IMAGES;i++)if(k->images[i].name&&same(name,k->images[i].name)){image=&k->images[i];break;}if(!image)return -2;
        if((r=vector(v,b,args,argv,&argc))||(r=vector(v,c,env,envp,&envc)))return r;
        uint32_t steps=v->steps;if(rv_replace_env(v,image->bytes,image->size,argc,argv,envc,envp))return -8;
        v->process_calls=1;v->steps=steps;for(unsigned i=0;i<FS_FDS;i++)if(p->fds.cloexec[i])fs_close(k->fs,&p->fds,i);*replaced=1;return 0;}
    case 260:{if((a==0||(a>0x7fffffffu&&a!=UINT32_MAX))||c>1||v->r[13])return -22;if(b&&!rv_check(v,b,4,RV_W))return -14;
        int exists;RPProcess *q=child(k,p,a,&exists);if(!exists)return -10;if(!q)return c?0:FS_BLOCK;
        uint32_t pid=q->result.pid,status=q->result.state==RP_EXITED?q->result.status<<8:q->result.state==RP_TRAPPED?4:9;RPResult ignored;
        if(b){write32(rv_buffer(v,b,4,1),status);}rp_reap(k,pid,&ignored);return (int32_t)pid;}
    default:return -38;
    }
}
int rp_tick(RPKernel *k,uint32_t quantum){
    if(!quantum||!k->fs)return -1;
    for(unsigned i=0;i<RP_SLOTS;i++){RPProcess *p=&k->slots[i];if(p->result.state==RP_BLOCKED&&(p->vm.r[17]==260?waiting_ready(k,p):fs_ready(k->fs,&p->fds,p->vm.r[10],p->vm.r[17]==64,p->vm.r[12]))){p->result.state=RP_READY;k->wakes++;}}
    for(unsigned i=0;i<RP_SLOTS;i++){
        unsigned j=(k->cursor+i)%RP_SLOTS;RPProcess *p=&k->slots[j];if(p->result.state!=RP_READY)continue;
        uint32_t left=p->limit-p->vm.steps,n=quantum<left?quantum:left;
        int r=rv_run(&p->vm,n,p->io,p->ctx,k->fs,&p->fds);k->cursor=(j+1)%RP_SLOTS;
        if(r==3){int replaced;int32_t value=process_call(k,p,&replaced);if(value==FS_BLOCK)r=2;else{if(!replaced){p->vm.r[10]=(uint32_t)value;p->vm.pc+=4;}p->vm.steps++;r=1;}}
        p->result.steps=p->vm.steps;
        if(r<0)finish(k,p,RP_TRAPPED,r);else if(!r)finish(k,p,RP_EXITED,0);else if(r==2){p->result.state=RP_BLOCKED;k->blocks++;}else if(p->vm.steps==p->limit)finish(k,p,RP_LIMIT,0);
        return 1;
    }return 0;
}
int rp_observe(const RPKernel *k,uint32_t pid,RPResult *out){if(!out)return -1;for(unsigned i=0;i<RP_SLOTS;i++){const RPProcess *p=&k->slots[i];if(p->result.state&&p->result.pid==pid){*out=p->result;return 0;}}return -1;}
int rp_cancel(RPKernel *k,uint32_t pid){RPProcess *p=find(k,pid);if(!p||(p->result.state!=RP_READY&&p->result.state!=RP_BLOCKED))return -1;finish(k,p,RP_CANCELLED,0);return 0;}
int rp_reap(RPKernel *k,uint32_t pid,RPResult *out){RPProcess *p=find(k,pid);if(!p||!out||(p->result.state==RP_READY||p->result.state==RP_BLOCKED))return -1;*out=p->result;p->result.state=RP_FREE;p->io=0;p->ctx=0;return 0;}
