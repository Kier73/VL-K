/* Guest-created computation: no host-created child or pipe. */
#include <stdint.h>
#define P(x) ((uint32_t)(uintptr_t)(x))
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a3 __asm__("a3")=d,a4 __asm__("a4")=e,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a7):"memory");return (int32_t)a0;}
#define SYS(n,a,b,c) call(n,a,b,c,0,0)
#define CHECK(x,n) do{if(!(x))return n;}while(0)
int main(int argc,char **argv){(void)argc;(void)argv;int p[2],status=-1;volatile uint32_t private=123;int parent=SYS(172,0,0,0);CHECK(parent>0,1);
    CHECK(SYS(59,0,0,0)==-14&&SYS(59,P(p),02000000,0)==0,2);
    CHECK(SYS(220,0,0,0)==-22,3);int pid=SYS(220,17,0,0);CHECK(pid>=0,4);
    if(!pid){private=456;CHECK(SYS(172,0,0,0)!=parent,5);CHECK(SYS(57,p[1],0,0)==0&&SYS(24,p[0],0,0)==0,6);
        const char *args[]={"worker","Q",0},*env[]={"MODE=vlk",0};
        CHECK(SYS(221,P("missing"),P(args),P(env))==-2&&SYS(221,P("bad"),P(args),P(env))==-8,7);
        CHECK(SYS(25,p[0],1,0)==1&&private==456&&SYS(221,P("worker"),1,P(env))==-14,8);
        SYS(221,P("worker"),P(args),P(env));return 9;
    }
    CHECK(SYS(57,p[0],0,0)==0&&SYS(260,pid,P(&status),1)==0&&status==-1,10);
    CHECK(SYS(260,pid,1,0)==-14&&SYS(220,17,0,0)==-11,11);
    static uint8_t data[8192];for(unsigned i=0;i<sizeof(data);i++)data[i]=(uint8_t)(i*13+7);
    unsigned sent=0;while(sent<sizeof(data)){int n=SYS(64,p[1],P(data+sent),sizeof(data)-sent);CHECK(n>0,12);sent+=(unsigned)n;}
    CHECK(SYS(57,p[1],0,0)==0&&SYS(260,pid,P(&status),0)==pid&&status==23*256&&private==123,13);
    CHECK(SYS(260,pid,P(&status),0)==-10,14);
    int next=SYS(220,17,0,0);CHECK(next>=0,15);if(!next)return 7;
    CHECK(next>pid&&SYS(260,-1,P(&status),0)==next&&status==7*256,16);
    static const char done[]="controller passed\n";return SYS(64,1,P(done),sizeof(done)-1)==sizeof(done)-1?0:17;
}
