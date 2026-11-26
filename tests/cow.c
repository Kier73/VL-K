#include "rvproc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RPKernel k;static RVFS fs;static uint8_t image[RV_SIZE],ram[2][RV_SIZE],oracle[2][64*RV_PAGE];static RV v[2];
static uint32_t seed=1234567;
static uint32_t random32(void){seed=seed*1664525u+1013904223u;return seed;}
static void setup(void){memset(v,0,sizeof(v));v[0].mem=ram[0];for(unsigned p=0;p<64;p++)v[0].pages[p]=RV_R|RV_W;for(unsigned i=0;i<sizeof(oracle[0]);i++)oracle[0][i]=ram[0][i]=(uint8_t)(random32()>>24);memcpy(oracle[1],oracle[0],sizeof(oracle[0]));assert(rv_fork_memory(&v[1],ram[1],&v[0])==64);assert(!v[0].cow_copies&&!v[1].cow_copies);}
static void differential(void){setup();for(unsigned i=0;i<5000;i++){unsigned side=random32()>>31,at=random32()%(sizeof(oracle[0])-8),n=1+random32()%4;if(random32()&0x100){uint8_t *p=rv_buffer(&v[side],at,n,1);for(unsigned j=0;j<n;j++)p[j]=oracle[side][at+j]=(uint8_t)(random32()>>24);}else{uint32_t expected=0;for(unsigned j=0;j<n;j++)expected|=(uint32_t)oracle[side][at+j]<<(8*j);assert(rv_word(&v[side],at,n)==expected);}}
    assert(v[0].cow_copies+v[1].cow_copies<=64);rv_release_memory(&v[0]);assert(!v[0].peer&&!v[1].peer&&!memcmp(v[1].mem,oracle[1],sizeof(oracle[1])));}
static int32_t stream(void *ctx,int wr,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;assert(wr&&fd==1&&n==21&&!memcmp(buf,"copy-on-write passed\n",21));return (int32_t)n;}
int main(int argc,char **argv){assert(argc==2);differential();setup();uint8_t prior=ram[0][0];assert(rv_word(&v[1],0,1)==prior&&!v[1].cow_copies);rv_release_memory(&v[1]);assert(!v[0].peer&&!v[0].cow_copies&&ram[0][0]==prior);
    /* Releasing the owner materializes the survivor, not a stale slot. */
    setup();rv_release_memory(&v[0]);assert(v[1].cow_copies==64&&!memcmp(ram[1],oracle[1],sizeof(oracle[1])));
    puts("5000 mixed memory-oracle operations, owner/borrower release and zero-copy fork passed");
    FILE *f=fopen(argv[1],"rb");assert(f);size_t n=fread(image,1,sizeof(image),f);assert(!ferror(f));fclose(f);k.fs=&fs;
    const char *args[]={"cow"};uint32_t quanta[]={1,31,1024,65536};unsigned min=UINT32_MAX,max=0,shared=0;
    for(unsigned i=0;i<4;i++){uint32_t pid;RPResult r;k.forks=k.shared_pages=0;k.cursor=0;assert(!rp_spawn(&k,image,n,1,args,2000000,stream,0,&pid));unsigned rounds=0;while(rp_tick(&k,quanta[i])>0)assert(++rounds<2000000);assert(!rp_reap(&k,pid,&r));if(r.state!=RP_EXITED||r.status)fprintf(stderr,"state=%u status=%u trap=%d\n",r.state,r.status,r.trap);assert(r.state==RP_EXITED&&!r.status&&k.forks==1&&k.shared_pages>=256);unsigned copies=0;for(unsigned j=0;j<RP_SLOTS;j++){assert(!k.slots[j].vm.peer&&k.slots[j].result.state==RP_FREE);copies+=k.slots[j].vm.cow_copies;}assert(copies<16);if(copies<min)min=copies;if(copies>max)max=copies;shared=k.shared_pages;for(unsigned j=0;j<FS_OPEN;j++)assert(!fs.opens[j].refs);}
    printf("four compiled fork workloads: %u shared pages at fork, %u..%u payload page copies through termination\n",shared,min,max);return 0;
}
