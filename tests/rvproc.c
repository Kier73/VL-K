#include "rvproc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RPKernel k;static RVFS fs;static uint8_t image[RV_SIZE];
static unsigned outputs[2];
static int32_t stream(void *ctx,int output,uint32_t fd,uint8_t *buf,uint32_t n){assert(output&&fd==1&&n==22&&!memcmp(buf,"descriptor ABI passed\n",22));outputs[*(unsigned*)ctx]++;return (int32_t)n;}
static void clean(void){for(unsigned i=0;i<FS_OPEN;i++)assert(!fs.opens[i].refs);}
int main(int argc,char **argv){assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);size_t n=fread(image,1,sizeof(image),f);assert(!ferror(f));fclose(f);k.fs=&fs;
    const char *a[]={"probe","left"},*b[]={"probe","right"};uint32_t p,q,untouched=42;unsigned zero=0,one=1;RPResult r,s;unsigned cases=0;
    for(unsigned quantum=1;quantum<=129;quantum=quantum*2+1){
        assert(rp_spawn(&k,image,1,2,a,100000,stream,&zero,&untouched)==-3&&untouched==42);
        assert(!rp_spawn(&k,image,n,2,a,100000,stream,&zero,&p));assert(!rp_spawn(&k,image,n,2,b,100000,stream,&one,&q)&&q==p+1);
        assert(rp_spawn(&k,image,n,2,b,100000,stream,&one,&untouched)==-2&&untouched==42);assert(rp_reap(&k,p,&r)<0&&rp_tick(&k,0)<0);
        assert(rp_tick(&k,quantum)==1);assert(!rp_observe(&k,p,&r)&&r.steps>0);assert(!rp_observe(&k,q,&s)&&s.steps==0);
        assert(rp_tick(&k,quantum)==1);assert(!rp_observe(&k,q,&s)&&s.steps>0);
        unsigned rounds=2;while(rp_tick(&k,quantum)>0)assert(++rounds<100000);
        assert(!rp_reap(&k,p,&r)&&!rp_reap(&k,q,&s)&&r.state==RP_EXITED&&s.state==RP_EXITED&&!r.status&&!s.status&&r.steps==s.steps);
        assert(rp_observe(&k,p,&r)<0&&rp_cancel(&k,q)<0);clean();
        assert(fs.files[0].size==5&&fs.files[1].size==5);uint8_t x[5],y[5];assert(fs_file_read(&fs,&fs.files[0],0,x,5)==5&&fs_file_read(&fs,&fs.files[1],0,y,5)==5&&!memcmp(x,"abcdE",5)&&!memcmp(x,y,5));
        assert(!fs_unlink(&fs,"left")&&!fs_unlink(&fs,"right"));cases++;
    }
    assert(outputs[0]==cases&&outputs[1]==cases);
    assert(!rp_spawn(&k,image,n,2,a,1,stream,&zero,&p)&&!rp_spawn(&k,image,n,2,b,100000,stream,&one,&q));
    assert(rp_tick(&k,100)==1);assert(!rp_observe(&k,p,&r)&&r.state==RP_LIMIT&&r.steps==1);assert(!rp_cancel(&k,q));assert(!rp_reap(&k,q,&s)&&s.state==RP_CANCELLED);assert(!rp_reap(&k,p,&r));clean();
    /* Valid ELF with invalid first opcode, not a simulated trap. */
    uint32_t off=(uint32_t)image[28]|(uint32_t)image[29]<<8|(uint32_t)image[30]<<16|(uint32_t)image[31]<<24;
    uint32_t at=(uint32_t)image[off+4]|(uint32_t)image[off+5]<<8|(uint32_t)image[off+6]<<16|(uint32_t)image[off+7]<<24;memset(image+at,255,4);
    assert(!rp_spawn(&k,image,n,2,a,100,stream,&zero,&p));assert(rp_tick(&k,10)==1);assert(!rp_reap(&k,p,&r)&&r.state==RP_TRAPPED&&r.trap==-3&&!r.steps);clean();
    printf("%u scheduling quanta, %u compiled process completions, exact file outputs, stale handles, capacity, cancellation, budget and trap cleanup passed\n",cases,cases*2);return 0;
}
