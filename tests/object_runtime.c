#include "rvproc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RPKernel k;static RVFS fs;static uint8_t image[RV_SIZE],demo[RV_SIZE],runtime[RV_SIZE];
static size_t load(const char *p,uint8_t *out){FILE *f=fopen(p,"rb");assert(f);size_t n=fread(out,1,RV_SIZE,f);assert(!ferror(f));fclose(f);return n;}
static int32_t stream(void *ctx,int wr,uint32_t fd,uint8_t *buf,uint32_t n){assert(wr&&fd==1);const char *expected=ctx;assert(n==strlen(expected)&&!memcmp(buf,expected,n));return (int32_t)n;}
static void clean(void){for(unsigned j=0;j<FS_OPEN;j++)assert(!fs.opens[j].refs);
#ifdef RV_OBJECT_BACKEND
    assert(!k.pool.reserved&&!k.pool.live&&!k.pool.dense);
#endif
}
int main(int argc,char **argv){assert(argc==4);size_t n=load(argv[1],image),d=load(argv[2],demo),m=load(argv[3],runtime);k.fs=&fs;
    const char *args[]={"cow"};const unsigned quanta[]={1,31,1024,65536};
    for(unsigned i=0;i<4;i++){uint32_t pid;RPResult r;k.cursor=0;k.forks=k.shared_pages=0;
        assert(!rp_spawn(&k,image,n,1,args,2000000,stream,"copy-on-write passed\n",&pid));unsigned rounds=0;
        while(rp_tick(&k,quanta[i])>0)assert(++rounds<2000000);
        assert(!rp_reap(&k,pid,&r)&&r.state==RP_EXITED&&!r.status&&k.forks==1&&k.shared_pages==273);clean();
        printf("cow quantum %u: %u retired instructions, %u shared mappings\n",quanta[i],r.steps,k.shared_pages);
    }
    const char *da[]={"demo","kernel"};uint32_t pid[4];for(unsigned i=0;i<4;i++)assert(!rp_spawn(&k,demo,d,2,da,1000000,stream,"demo 54c69d41\n",&pid[i]));
    unsigned rounds=0;while(rp_tick(&k,127)>0)assert(++rounds<1000000);
    for(unsigned i=0;i<4;i++){RPResult r;assert(!rp_reap(&k,pid[i],&r)&&r.state==RP_EXITED&&!r.status);printf("demo %u: %u retired instructions\n",i,r.steps);}clean();
#ifdef RV_OBJECT_BACKEND
    fprintf(stderr,"pool peak dense=%u, shared-object splits=%u\n",k.pool.peak_dense,k.pool.copies);
    /* Reserve all but 16 mappings; the 17+ page startup must fail without publication. */
    ROSpace holder={0};assert(!ro_map(&k.pool,&holder,0,RO_OBJECTS-16));uint32_t untouched=99;
    assert(rp_spawn(&k,demo,d,2,da,1000000,stream,"demo 54c69d41\n",&untouched)==-3&&untouched==99&&k.pool.reserved==RO_OBJECTS-16);
    ro_drop(&k.pool,&holder);clean();
    /* Direct runtime probe exercises auxv and memory map/protection/heap operations. */
    static RV v;RVFds fds={0};const char *ra[]={"runtime","kernel"},*env[]={"MODE=vlk"};
    assert(!rv_load_pool(&v,&k.pool,k.scratch,runtime,m,2,ra,1,env));fs_reset_fds(&fs,&fds);assert(!rv_run(&v,1000000,stream,"runtime ABI passed\n",&fs,&fds)&&!v.status);rv_release_memory(&v);fs_drop_fds(&fs,&fds);clean();
    fprintf(stderr,"capacity refusal and pooled runtime startup/mapping passed\n");
#else
    (void)m;
#endif
    return 0;
}
