#define _GNU_SOURCE
/* Same source on native POSIX and RV32: open-description and metadata semantics. */
#include <stdint.h>
#ifdef __riscv
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a3 __asm__("a3")=d,a4 __asm__("a4")=e,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a7):"memory");return (int32_t)a0;}
#define P(x) ((uint32_t)(uintptr_t)(x))
static int openfile(const char *p,int f){return call(56,-100,P(p),f,0600,0);}
static int closefile(int d){return call(57,d,0,0,0,0);}
static int dupfile(int d){return call(23,d,0,0,0,0);}
static int dupat(int d,int x){return call(24,d,x,02000000,0,0);}
static int ctl(int d,int c,int a){return call(25,d,c,a,0,0);}
static int wr(int d,const void *p,int n){return call(64,d,P(p),n,0,0);}
static int rd(int d,void *p,int n){return call(63,d,P(p),n,0,0);}
static int seek(int d,int n){uint32_t v[2];return call(62,d,0,n,P(v),0)?-1:(int)v[0];}
static int metadata(int d,const char *p,uint8_t *o){return call(291,d,P(p),*p?0:0x1000,0x7ff,P(o));}
#else
#include <unistd.h>
#include <fcntl.h>
#include <sys/syscall.h>
#include <sys/stat.h>
static int openfile(const char *p,int f){return open(p,f,0600);}
static int closefile(int d){return close(d);}
static int dupfile(int d){return dup(d);}
static int dupat(int d,int x){return (int)syscall(SYS_dup3,d,x,O_CLOEXEC);}
static int ctl(int d,int c,int a){return fcntl(d,c,a);}
static int wr(int d,const void *p,int n){return (int)write(d,p,n);}
static int rd(int d,void *p,int n){return (int)read(d,p,n);}
static int seek(int d,int n){return (int)lseek(d,n,SEEK_SET);}
static int metadata(int d,const char *p,uint8_t *o){return (int)syscall(SYS_statx,d,p,*p?0:0x1000,0x7ff,o);}
#endif
static uint32_t get(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
#define CHECK(x,n) do{if(!(x))return n;}while(0)
int main(int argc,char **argv){CHECK(argc==2,1);const char *name=argv[1];uint8_t a[256],b[256];char ch=0;
    int fd=openfile(name,0100|01000|2);CHECK(fd>=3,2);CHECK(wr(fd,"abcd",4)==4&&seek(fd,0)==0,3);
    int d=dupfile(fd),i=openfile(name,0);CHECK(d>=3&&i>=3&&d!=i,4);
    CHECK(rd(fd,&ch,1)==1&&ch=='a'&&rd(d,&ch,1)==1&&ch=='b'&&rd(i,&ch,1)==1&&ch=='a',5);
    CHECK(ctl(d,2,1)==0&&ctl(d,1,0)==1&&ctl(fd,1,0)==0,6);
    CHECK(ctl(d,4,02000)==0&&(ctl(fd,3,0)&02000),7);
    CHECK(wr(fd,"E",1)==1&&metadata(d,"",a)==0&&metadata(-100,name,b)==0,8);
    CHECK((get(a)&0x707)==0x707&&(get(a+28)&0170000)==0100000&&get(a+40)==5&&get(a+44)==0,9);
    CHECK(get(a+32)==get(b+32)&&get(a+36)==get(b+36)&&get(a+40)==get(b+40),10);
    CHECK(dupat(fd,12)==12&&ctl(12,1,0)==1&&dupat(fd,fd)<0,11);
    CHECK(closefile(fd)==0&&seek(d,0)==0&&rd(12,&ch,1)==1&&ch=='a',12);
    CHECK(closefile(d)==0&&closefile(i)==0&&closefile(12)==0,13);
    int out=dupfile(1);CHECK(out>=3,14);CHECK(wr(out,"descriptor ABI passed\n",22)==22&&closefile(out)==0,15);return 0;
}
