/* Standard read/write/exit ABI; native and guest builds use the same workload. */
#ifdef __riscv
static long call(long n,long x,void *p,unsigned count){register long a0 __asm__("a0")=x;register void *a1 __asm__("a1")=p;register unsigned a2 __asm__("a2")=count;register long a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a7):"memory");return a0;}
static long input(void *p,unsigned n){return call(63,0,p,n);}
static long output(void *p,unsigned n){return call(64,1,p,n);}
#else
#include <unistd.h>
static long input(void *p,unsigned n){return read(0,p,n);}
static long output(void *p,unsigned n){return write(1,p,n);}
#endif
int main(int argc,char **argv){unsigned char buf[1024];unsigned char key=argc>1?(unsigned char)argv[1][0]:0xa5;for(;;){long n=input(buf,sizeof(buf));if(n<0)return 3;if(!n)return 0;for(long i=0;i<n;i++)buf[i]^=key;long i=0;while(i<n){long k=output(buf+i,(unsigned)(n-i));if(k<=0)return 4;i+=k;}}}
