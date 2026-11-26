#include <stdint.h>
#define P(x) ((uint32_t)(uintptr_t)(x))
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e,uint32_t f){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a3 __asm__("a3")=d,a4 __asm__("a4")=e,a5 __asm__("a5")=f,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a5),"r"(a7):"memory");return (int32_t)a0;}
#define SYS(n,a,b,c) call(n,a,b,c,0,0,0)
#define CHECK(x,n) do{if(!(x))return n;}while(0)
#define N 256u
#define PAGE 4096u
int main(void){
    int32_t base=call(222,0,N*PAGE,3,0x22,~0u,0);CHECK(base>0,1);volatile uint8_t *p=(volatile uint8_t *)(uintptr_t)base;
    for(unsigned i=0;i<N;i++){p[i*PAGE]=(uint8_t)(i+1);p[i*PAGE+PAGE-1]=(uint8_t)(i^85);}
    CHECK(SYS(226,base+3*PAGE,PAGE,0)==0,2);
    int f[2],status=-1;CHECK(SYS(59,P(f),0,0)==0,3);int pid=SYS(220,17,0,0);CHECK(pid>=0,4);
    if(!pid){
        CHECK(SYS(57,f[1],0,0)==0,5);
        /* Read across a page boundary only after parent changed its own view. */
        CHECK(SYS(63,f[0],base+2*PAGE-4,8)==8,6);
        CHECK(p[0]==1&&p[PAGE]==2&&p[3*PAGE-1]==(uint8_t)(2^85),7);
        for(unsigned j=0;j<8;j++)CHECK(p[2*PAGE-4+j]==j+11,8);
        CHECK(SYS(226,base+3*PAGE,PAGE,3)==0&&p[3*PAGE]==4,9);
        p[3*PAGE]=90;p[0]=77;
        /* A borrowed page may be unmapped and reused without clearing the parent's page. */
        CHECK(SYS(215,base+(N-1)*PAGE,PAGE,0)==0,10);
        int32_t again=call(222,0,PAGE,3,0x22,~0u,0);CHECK(again==base+(N-1)*PAGE&&p[(N-1)*PAGE+PAGE-1]==0,11);
        p[(N-1)*PAGE+PAGE-1]=99;
        for(unsigned i=4;i<N-1;i++)CHECK(p[i*PAGE]==(uint8_t)(i+1)&&p[i*PAGE+PAGE-1]==(uint8_t)(i^85),12);
        return 23;
    }
    CHECK(SYS(57,f[0],0,0)==0,13);p[0]=99;uint8_t bytes[]={11,12,13,14,15,16,17,18};
    CHECK(SYS(64,f[1],P(bytes),8)==8&&SYS(57,f[1],0,0)==0,14);
    CHECK(SYS(260,pid,P(&status),0)==pid&&status==23*256,15);
    CHECK(SYS(226,base+3*PAGE,PAGE,3)==0,16);
    CHECK(p[0]==99&&p[PAGE]==2&&p[2*PAGE]==3&&p[3*PAGE]==4&&p[2*PAGE-1]==(uint8_t)(1^85)&&p[(N-1)*PAGE+PAGE-1]==(uint8_t)((N-1)^85),17);
    for(unsigned i=4;i<N;i++)CHECK(p[i*PAGE]==(uint8_t)(i+1),18);
    static const char msg[]="copy-on-write passed\n";return SYS(64,1,P(msg),sizeof(msg)-1)==sizeof(msg)-1?0:19;
}
