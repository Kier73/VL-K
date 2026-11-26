#include "rvproc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RPKernel k;static RVFS fs;static uint8_t image[RV_SIZE],input[65536],output[65536];
static uint32_t inpos,outpos;
static int32_t source(void *ctx,int wr,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;assert(!wr&&fd==0);if(n>sizeof(input)-inpos)n=sizeof(input)-inpos;memcpy(buf,input+inpos,n);inpos+=n;return (int32_t)n;}
static int32_t sink(void *ctx,int wr,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;assert(wr&&fd==1&&n<=sizeof(output)-outpos);memcpy(output+outpos,buf,n);outpos+=n;return (int32_t)n;}
static RPProcess *proc(uint32_t pid){for(unsigned i=0;i<RP_SLOTS;i++)if(k.slots[i].result.pid==pid)return &k.slots[i];assert(0);return 0;}
static void clean(void){for(unsigned i=0;i<FS_OPEN;i++)assert(!fs.opens[i].refs);for(unsigned i=0;i<FS_PIPES;i++)assert(!fs.pipes[i].readers&&!fs.pipes[i].writers&&!fs.pipes[i].size);}
int main(int argc,char **argv){assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);size_t n=fread(image,1,sizeof(image),f);assert(!ferror(f));fclose(f);k.fs=&fs;
    uint32_t x=1234567;for(unsigned i=0;i<sizeof(input);i++){x=x*1664525u+1013904223u;input[i]=(uint8_t)(x>>24);}
    const char *args[]={"filter","Q"};uint32_t a,b;RPResult r,s;uint32_t total_blocks=0,total_wakes=0;
    /* Native endpoint boundary: atomic small writes, duplication, EOF and EPIPE. */
    RVFds rd={0},wr={0};uint8_t buf[FS_PIPE_CAP];assert(!fs_pipe(&fs,&rd,&wr,0,1));
    assert(fs_read(&fs,&rd,0,buf,1)==FS_BLOCK&&!fs_ready(&fs,&rd,0,0,1));
    assert(fs_write(&fs,&wr,1,input,FS_PIPE_CAP-1)==FS_PIPE_CAP-1);assert(fs_write(&fs,&wr,1,input,2)==FS_BLOCK&&!fs_ready(&fs,&wr,1,1,2));
    assert(fs_read(&fs,&rd,0,buf,1)==1&&buf[0]==input[0]&&fs_ready(&fs,&wr,1,1,2));
    assert(fs_write(&fs,&wr,1,input,2)==2);assert(fs_dup(&fs,&wr,1,0,0,0)==0);assert(!fs_close(&fs,&wr,1));
    assert(fs_read(&fs,&rd,0,buf,FS_PIPE_CAP)==FS_PIPE_CAP&&!memcmp(buf,input+1,FS_PIPE_CAP-2)&&buf[FS_PIPE_CAP-2]==input[0]&&buf[FS_PIPE_CAP-1]==input[1]);
    assert(fs_read(&fs,&rd,0,buf,1)==FS_BLOCK);assert(!fs_close(&fs,&wr,0));assert(fs_read(&fs,&rd,0,buf,1)==0);assert(!fs_close(&fs,&rd,0));clean();
    assert(!fs_pipe(&fs,&rd,&wr,0,1));assert(!fs_close(&fs,&rd,0));assert(fs_write(&fs,&wr,1,input,1)==-32);fs_drop_fds(&fs,&wr);clean();
    const uint32_t quanta[]={1,7,127,1024,65536};
    for(unsigned i=0;i<sizeof(quanta)/sizeof(*quanta);i++){
        inpos=outpos=0;k.cursor=0;k.blocks=k.wakes=0;
        /* Consumer first: force an empty read, then let producer run. */
        assert(!rp_spawn(&k,image,n,2,args,3000000,sink,0,&b));assert(!rp_spawn(&k,image,n,2,args,3000000,source,0,&a));assert(!rp_connect(&k,a,b));
        unsigned rounds=0;while(rp_tick(&k,quanta[i])>0)assert(++rounds<1000000);
        assert(!rp_reap(&k,a,&r)&&!rp_reap(&k,b,&s)&&r.state==RP_EXITED&&s.state==RP_EXITED&&!r.status&&!s.status);
        assert(inpos==sizeof(input)&&outpos==sizeof(output)&&!memcmp(input,output,sizeof(input)));clean();total_blocks+=k.blocks;total_wakes+=k.wakes;
        printf("quantum %u: blocks %u, wakes %u, bytes %u\n",quanta[i],k.blocks,k.wakes,outpos);
    }
    /* A blocked instruction has no architectural effect. Cancel writer, wake reader on EOF. */
    inpos=outpos=0;k.cursor=0;assert(!rp_spawn(&k,image,n,2,args,3000000,sink,0,&b));assert(!rp_spawn(&k,image,n,2,args,3000000,source,0,&a));assert(!rp_connect(&k,a,b));
    assert(rp_tick(&k,65536)==1);RPProcess *p=proc(b);assert(p->result.state==RP_BLOCKED);uint32_t regs[32],pc=p->vm.pc,steps=p->vm.steps;memcpy(regs,p->vm.r,sizeof(regs));
    assert(!fs_ready(&fs,&p->fds,p->vm.r[10],0,p->vm.r[12]));assert(rp_reap(&k,b,&s)<0);
    assert(!rp_cancel(&k,a));assert(p->vm.pc==pc&&p->vm.steps==steps&&!memcmp(regs,p->vm.r,sizeof(regs)));while(rp_tick(&k,127)>0){}assert(!rp_reap(&k,b,&s)&&s.state==RP_EXITED&&!s.status&&!outpos);assert(!rp_reap(&k,a,&r)&&r.state==RP_CANCELLED);clean();
    printf("five compiled pipelines, %u bytes, %u blocked transitions / %u wakes; EOF, EPIPE, atomic write, reference and cancellation checks passed\n",5u*(unsigned)sizeof(input),total_blocks,total_wakes);return 0;
}
