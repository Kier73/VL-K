/* File utility: the same source runs on POSIX and the RV32 guest. */
#ifdef __riscv
static long call(long n,long x,long y,long z,long u,long v){register long a0 __asm__("a0")=x;register long a1 __asm__("a1")=y;register long a2 __asm__("a2")=z;register long a3 __asm__("a3")=u;register long a4 __asm__("a4")=v;register long a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a7):"memory");return a0;}
static long rd(int fd,void *p,unsigned n){return call(63,fd,(long)p,n,0,0);}
static long wr(int fd,const void *p,unsigned n){return call(64,fd,(long)p,n,0,0);}
static int op(const char *p,int flags){return (int)call(56,-100,(long)p,flags,0600,0);}
static int cl(int fd){return (int)call(57,fd,0,0,0,0);}
static int rm(const char *p){return (int)call(35,-100,(long)p,0,0,0);}
static long seek(int fd,long offset,int whence){unsigned result[2];long r=call(62,fd,offset<0?-1:0,offset,(long)result,whence);return r<0?r:(long)result[0];}
#else
#define _POSIX_C_SOURCE 200809L
#include <unistd.h>
#include <fcntl.h>
static long rd(int fd,void *p,unsigned n){return read(fd,p,n);}
static long wr(int fd,const void *p,unsigned n){return write(fd,p,n);}
static int op(const char *p,int flags){return open(p,flags,0600);}
static int cl(int fd){return close(fd);}
static int rm(const char *p){return unlink(p);}
static long seek(int fd,long offset,int whence){return lseek(fd,offset,whence);}
#endif
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int copy(int in,int out,int key){unsigned char buf[1024];for(;;){long n=rd(in,buf,sizeof(buf));if(n<0)return 4;if(!n)return 0;for(long i=0;i<n;i++)buf[i]^=(unsigned char)key;long pos=0;while(pos<n){long k=wr(out,buf+pos,(unsigned)(n-pos));if(k<=0)return 5;pos+=k;}}}
int main(int argc,char **argv){if(argc<3)return 2;const char *mode=argv[1],*name=argv[2];int a,b,r;
    if(eq(mode,"probe")){
        unsigned char v=0x51,z=0xff;
        a=op(name,0102|0200);if(a<0)return 10;
        if(op(name,0102|0200)>=0)return 11;
        b=op(name,0);if(b<0)return 12;
        if(seek(a,4095,0)!=4095||wr(a,&v,1)!=1||rd(b,&z,1)!=1||z!=0)return 13;
        if(seek(b,-1,2)!=4095||rd(b,&z,1)!=1||z!=v||rd(b,&z,1)!=0)return 14;
        if(wr(b,&v,1)>=0||seek(b,-4097,2)>=0||cl(b)<0||rd(b,&z,1)>=0)return 15;
        if(cl(a)<0)return 16;
        a=op(name,1|02000);if(a<0||seek(a,0,0)!=0||rd(a,&z,1)>=0||wr(a,&v,1)!=1||cl(a)<0)return 17;
        return 0;
    }
    if(eq(mode,"quota")){
        int handles[16];for(int i=0;i<16;i++){handles[i]=op(name,0102);if(handles[i]<0)return 10;}
        if(op(name,0)!=-24)return 11;
        for(int i=0;i<16;i++)if(cl(handles[i])<0)return 12;
        return rm(name)<0?13:0;
    }
    if(eq(mode,"rm"))return rm(name)<0?3:0;
    if(eq(mode,"count")){unsigned char c=0;a=op(name,0102);if(a<0)return 3;if(rd(a,&c,1)<0||seek(a,0,0)!=0)return 4;c++;if(wr(a,&c,1)!=1||cl(a)<0)return 5;char line[]="count 00\n";line[6]="0123456789abcdef"[c>>4];line[7]="0123456789abcdef"[c&15];return wr(1,line,9)==9?0:5;}
    if(eq(mode,"put")||eq(mode,"append")||eq(mode,"fail")){a=op(name,0101|(eq(mode,"append")?02000:01000));if(a<0)return 3;r=copy(0,a,0);cl(a);return r?r:(eq(mode,"fail")?19:0);}
    a=op(name,0);if(a<0)return 3;
    if(eq(mode,"tail")){if(seek(a,-16,2)<0){cl(a);return 4;}r=copy(a,1,0);cl(a);return r;}
    if(eq(mode,"get")){r=copy(a,1,0);cl(a);return r;}
    if(eq(mode,"xor")&&argc==4){b=op(argv[3],0101|01000);if(b<0){cl(a);return 3;}r=copy(a,b,0xa5);cl(a);cl(b);return r;}
    cl(a);return 2;}
