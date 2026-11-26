/* Small interpreted guest shell; no host parser, process creation or pipe setup. */
#include <stdint.h>
#define P(x) ((uint32_t)(uintptr_t)(x))
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a3 __asm__("a3")=d,a4 __asm__("a4")=e,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a4),"r"(a7):"memory");return (int32_t)a0;}
#define SYS(n,a,b,c) call(n,a,b,c,0,0)
static unsigned len(const char *s){unsigned n=0;while(s[n])n++;return n;}
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int emit(int fd,const char *s){unsigned n=len(s);while(n){int k=SYS(64,fd,P(s),n);if(k<=0)return -1;s+=k;n-=(unsigned)k;}return 0;}
static int launch(char *name,char *arg,char *data){int fds[2],status;if(data&&SYS(59,P(fds),02000000,0))return -1;
    int pid=SYS(220,17,0,0);if(pid<0){if(data){SYS(57,fds[0],0,0);SYS(57,fds[1],0,0);}return -1;}
    if(!pid){if(data){SYS(57,fds[1],0,0);if(SYS(24,fds[0],0,0)<0){SYS(93,126,0,0);return -1;}}const char *args[]={name,arg,0};SYS(221,P(name),P(args),0);SYS(93,127,0,0);return -1;}
    int failed=0;if(data){SYS(57,fds[0],0,0);failed=emit(fds[1],data);SYS(57,fds[1],0,0);}
    return SYS(260,pid,P(&status),0)==pid&&!status&&!failed?0:-1;
}
int main(void){char line[128],*words[6];for(;;){if(emit(1,"guest> "))return 2;unsigned n=0;int overflow=0;
        for(;;){char c;int r=SYS(63,0,P(&c),1);if(r<0)return 3;if(!r&&!n)return 0;if(!r||c=='\n')break;if(c=='\r')continue;if(n<sizeof(line)-1)line[n++]=c;else overflow=1;}
        line[n]=0;if(overflow){emit(1,"invalid\n");continue;}unsigned count=0;char *p=line;
        while(*p){while(*p==' ')p++;if(!*p)break;if(count==6){count=7;break;}words[count++]=p;while(*p&&*p!=' ')p++;if(*p)*p++=0;}
        if(count==1&&eq(words[0],"quit"))return 0;
        int r=-1;if((count==2||count==3)&&eq(words[0],"run"))r=launch(words[1],count==3?words[2]:0,0);
        else if((count==4||count==5)&&eq(words[0],"send")&&eq(words[2],"|"))r=launch(words[3],count==5?words[4]:0,words[1]);
        else {emit(1,"invalid\n");continue;}emit(1,r?"failed\n":"ok\n");
    }}
