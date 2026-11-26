#include <stdint.h>
#define P(x) ((uint32_t)(uintptr_t)(x))
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a7):"memory");return (int32_t)a0;}
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
int main(int argc,char **argv){if(argc!=2||!eq(argv[1],"Q")||!argv[3]||!eq(argv[3],"MODE=vlk")||argv[4])return 30;
    if(call(25,3,1,0)!=-9)return 31;uint8_t data[257];unsigned total=0;
    for(;;){int n=call(63,0,P(data),sizeof(data));if(n<0)return 32;if(!n)break;for(int i=0;i<n;i++){if(data[i]!=(uint8_t)((total+(unsigned)i)*13+7))return 33;data[i]^=81;}total+=(unsigned)n;if(call(64,1,P(data),n)!=n)return 34;}
    return total==8192?23:35;
}
