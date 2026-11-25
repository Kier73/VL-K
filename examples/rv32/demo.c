/* Unchanged C source compiled for native Linux and RV32IM. */
#include <stdint.h>
#ifdef __riscv
static long output(const void *p,unsigned n){register long a0 __asm__("a0")=1;register const void *a1 __asm__("a1")=p;register unsigned a2 __asm__("a2")=n;register long a7 __asm__("a7")=64;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a7):"memory");return a0;}
#else
#include <unistd.h>
static long output(const void *p,unsigned n){return write(1,p,n);}
#endif
static volatile uint32_t state[256];
static void hex(uint32_t x,char *p){for(unsigned i=0;i<8;i++)p[i]="0123456789abcdef"[(x>>(28-4*i))&15];}
int main(int argc,char **argv){uint32_t x=0x12345678;for(int i=1;i<argc;i++)for(char *p=argv[i];*p;p++)x=(x^(uint8_t)*p)*16777619u;for(unsigned i=0;i<256;i++){if(state[i])return 11;state[i]=x=x*1664525u+1013904223u;}for(unsigned j=0;j<3000;j++){unsigned i=(x>>8)&255;uint32_t y=state[i];x=(x^(y/(j+1)))+(y%(j+1));state[i]=x;}char buf[]="demo 00000000\n";hex(x,buf+5);return output(buf,sizeof(buf)-1)==sizeof(buf)-1?0:12;}
