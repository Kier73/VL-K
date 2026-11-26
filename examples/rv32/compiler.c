/* Guest-hosted postfix compiler: unsigned 32-bit expressions, byte I/O, ELF32/RV32IM. */
#include <stdint.h>
#define P(x) ((uint32_t)(uintptr_t)(x))
static int32_t call(uint32_t n,uint32_t a,uint32_t b,uint32_t c,uint32_t d){register uint32_t a0 __asm__("a0")=a,a1 __asm__("a1")=b,a2 __asm__("a2")=c,a3 __asm__("a3")=d,a7 __asm__("a7")=n;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a7):"memory");return (int32_t)a0;}
#define SYS(n,a,b,c) call(n,a,b,c,0)
#define MAX_WORDS 2048u
#define MAX_NODES 128u
#define ENTRY 0x10000u
static uint8_t image[84+4*MAX_WORDS];static unsigned words,failed;
static void put(unsigned at,unsigned n,uint32_t v){for(unsigned i=0;i<n;i++)image[at+i]=(uint8_t)(v>>(8*i));}
static void emit(uint32_t w){if(words==MAX_WORDS){failed=1;return;}put(84+4*words++,4,w);}
static uint32_t ins_i(uint32_t imm,unsigned rs,unsigned f,unsigned rd,unsigned op){return ((imm&4095u)<<20)|(rs<<15)|(f<<12)|(rd<<7)|op;}
static void li(unsigned rd,uint32_t x){uint32_t hi=(x+0x800u)&0xfffff000u;emit(hi|(rd<<7)|0x37);emit(ins_i(x-hi,rd,0,rd,0x13));}
static void push(void){emit(ins_i(-4u,2,0,2,0x13));emit(0x00512023u);} /* sw t0,0(sp) */
static void pop(void){emit(ins_i(0,2,2,6,3));emit(ins_i(4,2,0,2,0x13));}
static void terminate(unsigned code){li(10,code);li(17,93);emit(0x73);}
/* Exit with status 70 if a single-byte I/O operation did not return one. */
static void checked_io(unsigned syscall){li(10,syscall==63?0:1);emit(ins_i(0,2,0,11,0x13));li(12,1);li(17,syscall);emit(0x73);li(6,1);emit(0x00650c63u);terminate(70);}
enum {LIT,INPUT,ADD,SUB,MUL,XOR,SHR,DIV};
typedef struct {unsigned op,left,right;uint32_t value;} Node;
static Node nodes[MAX_NODES];static unsigned count,stack[MAX_NODES],depth;
static unsigned node(unsigned op,unsigned l,unsigned r,uint32_t value){if(count==MAX_NODES){failed=1;return 0;}nodes[count]=(Node){op,l,r,value};return count++;}
static uint32_t eval(unsigned op,uint32_t a,uint32_t b){switch(op){case ADD:return a+b;case SUB:return a-b;case MUL:return a*b;case SHR:return a>>(b&31);case DIV:return b?a/b:~0u;default:return a^b;}}
static void compile(unsigned idx){Node *n=&nodes[idx];if(failed)return;
    if(n->op==LIT){li(5,n->value);return;}
    if(n->op==INPUT){emit(ins_i(-4u,2,0,2,0x13));checked_io(63);emit(ins_i(0,2,4,5,3));emit(ins_i(4,2,0,2,0x13));return;}
    compile(n->left);push();compile(n->right);pop();
    /* t0 = t1 op t0; left evaluated before right, including input effects. */
    unsigned f=n->op==XOR?4:(n->op==SHR||n->op==DIV)?5:0,hi=n->op==SUB?32:(n->op==MUL||n->op==DIV)?1:0;emit((hi<<25)|(5u<<20)|(6u<<15)|(f<<12)|(5u<<7)|0x33);
}
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int token(char *s){unsigned op;uint32_t v=0;
    if(eq(s,"out")){if(depth!=1)return -1;compile(stack[0]);push();checked_io(64);emit(ins_i(4,2,0,2,0x13));depth=count=0;return failed?-1:0;}
    if(eq(s,"in"))stack[depth++]=node(INPUT,0,0,0);
    else if(eq(s,"add")||eq(s,"sub")||eq(s,"mul")||eq(s,"xor")||eq(s,"shr")||eq(s,"div")){if(depth<2)return -1;op=eq(s,"add")?ADD:eq(s,"sub")?SUB:eq(s,"mul")?MUL:eq(s,"shr")?SHR:eq(s,"div")?DIV:XOR;unsigned r=stack[--depth],l=stack[--depth];
        if(nodes[l].op==LIT&&nodes[r].op==LIT){stack[depth++]=node(LIT,0,0,eval(op,nodes[l].value,nodes[r].value));}else stack[depth++]=node(op,l,r,0);
    }else{if(!*s)return -1;for(;*s;s++){unsigned d=(unsigned char)*s-'0';if(d>9||v>(0xffffffffu-d)/10u)return -1;v=v*10u+d;}stack[depth++]=node(LIT,0,0,v);}
    return failed||depth>=MAX_NODES?-1:0;
}
static int writeall(int fd,const uint8_t *b,unsigned n){while(n){int k=SYS(64,fd,P(b),n);if(k<=0||(unsigned)k>n)return -1;b+=k;n-=(unsigned)k;}return 0;}
int main(int argc,char **argv){if(argc!=2)return 2;char s[16];unsigned n=0,total=0,outs=0;
    for(;;){char c;int r=SYS(63,0,P(&c),1);if(r<0)return 3;if(!r||c==','){if(!n)return 4;s[n]=0;if(eq(s,"out"))outs++;if(token(s))return 4;n=0;if(!r)break;}else{if(++total>1024||n==sizeof(s)-1||!c)return 4;s[n++]=c;}}
    if(depth||!outs||failed)return 4;terminate(0);if(failed)return 4;
    /* Fresh ELF header and a single R-X segment containing emitted instructions. */
    put(0,4,0x464c457f);put(4,4,0x00010101);put(16,2,2);put(18,2,243);put(20,4,1);put(24,4,ENTRY);put(28,4,52);put(40,2,52);put(42,2,32);put(44,2,1);
    put(52,4,1);put(56,4,84);put(60,4,ENTRY);put(64,4,ENTRY);put(68,4,words*4);put(72,4,words*4);put(76,4,5);put(80,4,4);
    if(eq(argv[1],"-"))return writeall(1,image,84+words*4)?5:0;
    int fd=call(56,-100,P(argv[1]),0100|0200|1,0600);if(fd<0)return 5;
    int ok=!writeall(fd,image,84+words*4)&&!SYS(52,fd,0755,0);if(SYS(57,fd,0,0))ok=0;if(!ok){SYS(35,-100,P(argv[1]),0);return 5;}return 0;
}
