/* A compiled guest installs an ELF from stdin, then launches it from its own FS. */
#include <stdint.h>
#define P(x) ((uint32_t)(uintptr_t)(x))
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a3 __asm__("a3")=d,a4 __asm__("a4")=e,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a7):"memory");return (int32_t)a0;}
#define SYS(n,a,b,c) call(n,a,b,c,0,0)
#define CHECK(x,n) do{if(!(x))return n;}while(0)
static int openfile(const char *name,uint32_t flags){return call(56,-100,P(name),flags,0666,0);}
static int execute(const char *name){const char *args[]={"demo","kernel",0};return SYS(221,P(name),P(args),0);}
static int child(const char *name){int pid=SYS(220,17,0,0),status=-1;if(pid<0)return -1;if(!pid){execute(name);SYS(93,126,0,0);return -1;}return SYS(260,pid,P(&status),0)==pid?status:-1;}
int main(void){
    static uint8_t buf[1024],st[256];
    CHECK(execute("./tool")==-2&&execute("../tool")==-22,1);
    int fd=openfile("tool",0102);CHECK(fd>=3,2);
    unsigned total=0;for(;;){int n=SYS(63,0,P(buf),sizeof(buf));CHECK(n>=0,3);if(!n)break;CHECK(SYS(64,fd,P(buf),n)==n,4);total+=(unsigned)n;}
    CHECK(total>52&&execute("./tool")==-13,5);
    CHECK(SYS(52,fd,04755,0)==-22&&SYS(52,fd,0755,0)==0&&execute("./tool")==-26,6);
    CHECK(call(291,-100,P("tool"),0,0x7ff,P(st))==0&&((unsigned)st[28]|(unsigned)st[29]<<8)==0100755,7);
    CHECK(SYS(57,fd,0,0)==0&&child("./tool")==0&&child("tool")==0,8);
    fd=openfile("tool",0);CHECK(fd>=3&&SYS(52,fd,0500,0)==0&&openfile("tool",1)==-13,9);
    CHECK(SYS(52,fd,0600,0)==0&&execute("./tool")==-13&&SYS(57,fd,0,0)==0,10);
    fd=openfile("tool",01002);CHECK(fd>=3&&SYS(64,fd,P("bad"),3)==3&&SYS(52,fd,0700,0)==0&&SYS(57,fd,0,0)==0,11);
    CHECK(execute("./tool")==-8&&SYS(35,-100,P("tool"),0)==0,12);
    fd=openfile("tool",0102);CHECK(fd>=3&&execute("./tool")==-13&&SYS(57,fd,0,0)==0,13);
    static const char done[]="filesystem executable passed\n";return SYS(64,1,P(done),sizeof(done)-1)==sizeof(done)-1?0:14;
}
