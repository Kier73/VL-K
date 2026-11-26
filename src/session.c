/* Hosted entry to the same freestanding process kernel. Guest names never become host paths. */
#include "rvproc.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
static RPKernel k;static RVFS fs;static uint8_t root[RV_SIZE],images[RP_IMAGES][RV_SIZE];
static size_t load(const char *path,uint8_t *out){FILE *f=fopen(path,"rb");if(!f)return 0;size_t n=fread(out,1,RV_SIZE,f);if(ferror(f)||fgetc(f)!=EOF)n=0;fclose(f);return n;}
static int32_t stream(void *ctx,int wr,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;ssize_t r=wr?write((int)fd,buf,n):read((int)fd,buf,n);return r<0?-errno:(int32_t)r;}
int main(int argc,char **argv){if(argc<2||argc>2+(int)RP_IMAGES){fprintf(stderr,"usage: vlk session ROOT [NAME=ELF ...]\n");return 2;}k.fs=&fs;size_t n=load(argv[1],root);if(!n)return 125;
    for(int i=2;i<argc;i++){char *eq=strchr(argv[i],'=');if(!eq)return 2;*eq=0;size_t size=load(eq+1,images[i-2]);if(!size||rp_register(&k,argv[i],images[i-2],size))return 125;}
    const char *args[]={argv[1]};uint32_t pid;RPResult r;if(rp_spawn(&k,root,n,1,args,100000000,stream,0,&pid))return 125;
    while(rp_tick(&k,1024)>0){}
    if(rp_reap(&k,pid,&r)||r.state!=RP_EXITED){fprintf(stderr,"vlk session: root did not exit normally\n");return 125;}
    for(unsigned i=0;i<RP_SLOTS;i++)if(k.slots[i].result.state){fprintf(stderr,"vlk session: unreaped or blocked child\n");return 125;}
    return (int)r.status;
}
