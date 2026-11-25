#include "rv32.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RVFS fs;static RVFds a,b;static RV va,vb;static uint8_t ma[RV_SIZE],mb[RV_SIZE],image[RV_SIZE];
static unsigned outputs[2];
static int32_t io(void *ctx,int output,uint32_t fd,uint8_t *buf,uint32_t n){assert(output&&fd==1&&n==22&&!memcmp(buf,"descriptor ABI passed\n",22));outputs[*(unsigned*)ctx]++;return (int32_t)n;}
int main(int argc,char **argv){assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);size_t n=fread(image,1,sizeof(image),f);assert(!ferror(f));fclose(f);
    fs_reset_fds(&fs,&a);fs_reset_fds(&fs,&b);
    int x=fs_open(&fs,&a,"shared",0102),y=fs_open(&fs,&b,"shared",2);assert(x==3&&y==3);
    assert(fs_write(&fs,&a,x,(const uint8_t*)"xyz",3)==3);uint8_t c;assert(fs_read(&fs,&b,y,&c,1)==1&&c=='x');
    int z=fs_dup(&fs,&b,y,0,0,0);assert(z==4&&fs_read(&fs,&b,z,&c,1)==1&&c=='y');
    assert(fs_unlink(&fs,"shared")==-16);fs_drop_fds(&fs,&a);assert(fs_read(&fs,&b,y,&c,1)==1&&c=='z');fs_drop_fds(&fs,&b);assert(!fs_unlink(&fs,"shared"));
    for(unsigned i=0;i<FS_OPEN;i++)assert(!fs.opens[i].refs);
    const char *aa[]={"probe","left"},*bb[]={"probe","right"};assert(!rv_load(&va,ma,image,n,2,aa)&&!rv_load(&vb,mb,image,n,2,bb));
    fs_reset_fds(&fs,&a);fs_reset_fds(&fs,&b);unsigned p=0,q=1,round=0;int ra=1,rb=1;
    while(ra==1||rb==1){assert(++round<10000);if(ra==1)ra=rv_run(&va,7,io,&p,&fs,&a);if(rb==1)rb=rv_run(&vb,11,io,&q,&fs,&b);}
    assert(!ra&&!rb&&!va.status&&!vb.status&&outputs[0]==1&&outputs[1]==1);assert(va.mem!=vb.mem);fs_drop_fds(&fs,&a);fs_drop_fds(&fs,&b);for(unsigned i=0;i<FS_OPEN;i++)assert(!fs.opens[i].refs);
    assert(!fs_unlink(&fs,"left")&&!fs_unlink(&fs,"right"));printf("two interleaved guests, %u scheduler rounds, isolated tables and shared files; all references released\n",round);return 0;
}
