#include <stdint.h>
/* Staged pure register program; serialized instance-local ABI. */
#define R 4u
#define D 5u
#define N 64u
enum { SET=1,COPY,ADD,MUL,ADDR,MULR };
typedef struct { uint32_t op,d,x; } Ins;
static Ins code[N];
static uint32_t seed[R],out[R],len,work,method,ready;
void vk1_begin(void) { len=work=method=ready=0; for(unsigned i=0;i<R;i++) seed[i]=0; }
int32_t vk1_seed(uint32_t r,uint32_t v) { if(r>=R) return -1; seed[r]=v; ready=0; return 0; }
int32_t vk1_append(uint32_t op,uint32_t d,uint32_t x) {
    if(op<SET || op>MULR || d>=R || ((op==COPY || op==ADDR || op==MULR) && x>=R)) return -1;
    if(len==N) return -2;
    code[len++]=(Ins){op,d,x}; ready=0; return 0;
}
uint32_t vk1_work(void) { return work; }
uint32_t vk1_method(void) { return method; }
uint32_t vk1_result(uint32_t r) { return ready && r<R ? out[r] : 0; }
static uint64_t ground_cost(uint64_t n) {
    uint64_t c=(uint64_t)len*D;
    while(n) { if(n&1) c+=D*D; n>>=1; if(n) c+=D*D*D; }
    return c;
}
int32_t vk1_run(uint64_t n,uint32_t budget,uint32_t mode) {
    uint32_t x[D],m[D][D],tmp[D][D],v[D];
    ready=work=method=0;
    if(mode>2) return -1;
    for(unsigned i=0;i<R;i++) x[i]=seed[i];
    x[R]=1;
    if(!n || !len) { for(unsigned i=0;i<R;i++) out[i]=x[i]; ready=1; return 0; }
    unsigned affine=1;
    for(unsigned k=0;k<len;k++) if(code[k].op==MULR) affine=0;
    if(mode==2 && !affine) return -1;
    uint64_t gc=ground_cost(n);
    unsigned use=affine && (mode==2 || (mode==0 && n>gc/len));
    if(use) {
        if(gc>budget) return -4;
        for(unsigned i=0;i<D;i++) for(unsigned j=0;j<D;j++) m[i][j]=(i==j);
        for(unsigned k=0;k<len;k++) {
            Ins q=code[k];
            for(unsigned j=0;j<D;j++) {
                uint32_t *p=&m[q.d][j];
                switch(q.op) {
                case SET: *p=j==R?q.x:0; break;
                case COPY: *p=m[q.x][j]; break;
                case ADD: if(j==R) *p+=q.x; break;
                case MUL: *p*=q.x; break;
                case ADDR: *p+=m[q.x][j]; break;
                }
            }
        }
        while(n) {
            if(n&1) {
                for(unsigned i=0;i<D;i++) { v[i]=0; for(unsigned j=0;j<D;j++) v[i]+=m[i][j]*x[j]; }
                for(unsigned i=0;i<D;i++) x[i]=v[i];
            }
            n>>=1;
            if(n) {
                for(unsigned i=0;i<D;i++) for(unsigned j=0;j<D;j++) { tmp[i][j]=0; for(unsigned k=0;k<D;k++) tmp[i][j]+=m[i][k]*m[k][j]; }
                for(unsigned i=0;i<D;i++) for(unsigned j=0;j<D;j++) m[i][j]=tmp[i][j];
            }
        }
        work=(uint32_t)gc; method=2;
    } else {
        if(n>budget/len) return -4;
        work=(uint32_t)(n*len); method=1;
        while(n--) for(unsigned k=0;k<len;k++) {
            Ins q=code[k]; uint32_t *p=&x[q.d];
            switch(q.op) {
            case SET: *p=q.x; break; case COPY: *p=x[q.x]; break;
            case ADD: *p+=q.x; break; case MUL: *p*=q.x; break;
            case ADDR: *p+=x[q.x]; break; case MULR: *p*=x[q.x]; break;
            }
        }
    }
    for(unsigned i=0;i<R;i++) out[i]=x[i];
    ready=1; return 0;
}
