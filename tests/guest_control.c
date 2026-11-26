#include "rvproc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RPKernel k;static RVFS fs;static uint8_t control[RV_SIZE],worker[RV_SIZE],output[9000],bad[1];static unsigned used;
static size_t load(const char *name,uint8_t *bytes){FILE *f=fopen(name,"rb");assert(f);size_t n=fread(bytes,1,RV_SIZE,f);assert(!ferror(f));fclose(f);return n;}
static int32_t io(void *ctx,int wr,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;assert(wr&&fd==1&&n<=sizeof(output)-used);memcpy(output+used,buf,n);used+=n;return (int32_t)n;}
int main(int argc,char **argv){assert(argc==3);size_t a=load(argv[1],control),b=load(argv[2],worker);k.fs=&fs;assert(!rp_register(&k,"worker",worker,b)&&!rp_register(&k,"bad",bad,sizeof(bad))&&rp_register(&k,"worker",worker,b)<0);
    const char *args[]={"controller"};const unsigned quanta[]={1,7,127,1024,65536};unsigned waits=0;
    for(unsigned i=0;i<sizeof(quanta)/sizeof(*quanta);i++){uint32_t pid;RPResult r;used=0;k.cursor=k.blocks=k.wakes=0;assert(!rp_spawn(&k,control,a,1,args,3000000,io,0,&pid));unsigned rounds=0,waiting=0;
        while(rp_tick(&k,quanta[i])>0){assert(++rounds<1000000);for(unsigned j=0;j<RP_SLOTS;j++){RPProcess *p=&k.slots[j];if(p->result.state==RP_BLOCKED&&p->vm.r[17]==260)waiting=1;}}
        assert(!rp_reap(&k,pid,&r));if(r.state!=RP_EXITED||r.status)fprintf(stderr,"state %u status %u trap %d steps %u output %u\n",r.state,r.status,r.trap,r.steps,used);assert(r.state==RP_EXITED&&!r.status);assert(used==8192+18&&!memcmp(output+8192,"controller passed\n",18));for(unsigned j=0;j<8192;j++)assert(output[j]==((uint8_t)(j*13+7)^81));
        for(unsigned j=0;j<RP_SLOTS;j++)assert(k.slots[j].result.state==RP_FREE);
        for(unsigned j=0;j<FS_OPEN;j++)assert(!fs.opens[j].refs);
        for(unsigned j=0;j<FS_PIPES;j++)assert(!fs.pipes[j].readers&&!fs.pipes[j].writers&&!fs.pipes[j].size);
        assert(k.blocks==k.wakes);waits+=waiting;printf("quantum %u: exact output, %u blocks and wakes, wait suspended %u\n",quanta[i],k.blocks,waiting);
    }assert(waits);puts("five guest-created pipelines, ten child lifecycles, isolated fork memory, admitted exec, wait and cleanup passed");return 0;
}
