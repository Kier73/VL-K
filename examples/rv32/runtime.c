/* Startup and anonymous-memory ABI probe, not a libc application. */
#include <stdint.h>
extern void _start(void);
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e,uint32_t f){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a3 __asm__("a3")=d,a4 __asm__("a4")=e,a5 __asm__("a5")=f,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a5),"r"(a7):"memory");return (int32_t)a0;}
#define SYS(n,a,b,c) call(n,a,b,c,0,0,0)
#define REQUIRE(c,n) do{if(!(c))return n;}while(0)
int runtime(uint32_t *sp){
    REQUIRE(((uintptr_t)sp&15)==0&&sp[0]==2&&sp[3]==0,10);
    REQUIRE(eq((const char *)(uintptr_t)sp[2],"kernel")&&sp[4]&&eq((const char *)(uintptr_t)sp[4],"MODE=vlk")&&sp[5]==0,11);
    uint32_t ph=0,phent=0,phnum=0,page=0,entry=0,execfn=0,base=1;
    for(uint32_t *a=sp+6;*a;a+=2){switch(a[0]){case 3:ph=a[1];break;case 4:phent=a[1];break;case 5:phnum=a[1];break;case 6:page=a[1];break;case 7:base=a[1];break;case 9:entry=a[1];break;case 31:execfn=a[1];break;}}
    REQUIRE(ph&&phent==32&&phnum>=1&&page==4096&&entry==(uintptr_t)_start&&execfn==sp[1]&&!base,12);
    REQUIRE(*(uint32_t *)(uintptr_t)ph==1,13);
    int32_t addr=call(222,0,8192,3,0x22,~0u,0);REQUIRE(addr>0,14);
    volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)addr;
    REQUIRE(p[0]==0&&p[1024]==0,15);p[0]=0x12345678;p[1024]=0xabcdef01;
    REQUIRE(SYS(226,addr,4096,0)==0,16);
    REQUIRE(SYS(64,1,addr,1)==-14,17);
    REQUIRE(SYS(226,addr-4096,12288,3)==-12&&SYS(64,1,addr,1)==-14,18);
    REQUIRE(SYS(226,addr,4096,3)==0&&p[0]==0x12345678&&p[1024]==0xabcdef01,19);
    REQUIRE(SYS(226,addr,4096,7)==-22&&SYS(215,addr-4096,12288,0)==-12&&p[0]==0x12345678,20);
    int32_t brk=SYS(214,0,0,0);REQUIRE(SYS(214,addr+4096,0,0)==brk,21);
    REQUIRE(SYS(215,addr,8192,0)==0&&SYS(64,1,addr,1)==-14,22);
    int32_t again=call(222,0,8192,3,0x22,~0u,0);REQUIRE(again==addr&&p[0]==0&&p[1024]==0,23);
    REQUIRE(call(222,0,0,3,0x22,~0u,0)==-22&&call(222,0,4096,3,0x32,~0u,0)==-22,24);
    REQUIRE(SYS(215,addr,8192,0)==0,25);
    static const char msg[]="runtime ABI passed\n";
    return SYS(64,1,(uintptr_t)msg,sizeof(msg)-1)==sizeof(msg)-1?0:26;
}
