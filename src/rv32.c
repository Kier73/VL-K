#include "rv32.h"
static uint32_t get(const uint8_t *p,unsigned n){uint32_t v=0;for(unsigned i=0;i<n;i++)v|=(uint32_t)p[i]<<(8*i);return v;}
static void put(uint8_t *p,unsigned n,uint32_t v){for(unsigned i=0;i<n;i++)p[i]=(uint8_t)(v>>(8*i));}
static uint32_t sx(uint32_t v,unsigned n){uint32_t bit=1u<<(n-1);return (v^bit)-bit;}
static int span(uint32_t a,uint32_t n){return a<=RV_SIZE && n<=RV_SIZE-a;}
static int access(RV *v,uint32_t a,uint32_t n,unsigned flags){if(!span(a,n))return 0;if(!n)return 1;for(uint32_t p=a/RV_PAGE;p<=(a+n-1)/RV_PAGE;p++)if((v->pages[p]&flags)!=flags)return 0;return 1;}
int rv_check(RV *v,uint32_t a,uint32_t n,unsigned flags){return access(v,a,n,flags);}
static void zero(uint8_t *p,size_t n){for(size_t i=0;i<n;i++)p[i]=0;}
/* Two-context COW: a borrowed page resolves to the peer's private backing.
 * A writer preserves the other observation before changing its own bytes. */
static void private_page(RV *v,uint32_t p){
    if(!v->borrowed[p])return;
    uint32_t at=p*RV_PAGE;
    for(unsigned j=0;j<RV_PAGE;j++)((volatile uint8_t *)v->mem)[at+j]=v->peer->mem[at+j];
    v->borrowed[p]=0;v->cow_copies++;
}
static const uint8_t *address(RV *v,uint32_t a){return (v->borrowed[a/RV_PAGE]?v->peer->mem:v->mem)+a;}
uint32_t rv_word(RV *v,uint32_t a,unsigned n){
#ifdef RV_OBJECT_BACKEND
    if(v->pool){uint8_t b[4];ro_read(v->pool,&v->space,a,b,n);return get(b,n);}
#endif
    if(n<=RV_PAGE-a%RV_PAGE)return get(address(v,a),n);
    uint32_t x=0;for(unsigned j=0;j<n;j++)x|=(uint32_t)*address(v,a+j)<<(8*j);return x;
}
uint8_t *rv_buffer(RV *v,uint32_t a,uint32_t n,int write){
    if(n)for(uint32_t p=a/RV_PAGE;p<=(a+n-1)/RV_PAGE;p++){
        private_page(v,p);if(write&&v->peer)private_page(v->peer,p);
    }
    return v->mem+a;
}
void rv_read_bytes(RV *v,uint32_t a,uint8_t *out,uint32_t n){
#ifdef RV_OBJECT_BACKEND
    if(v->pool){ro_read(v->pool,&v->space,a,out,n);return;}
#endif
    for(uint32_t i=0;i<n;i++)out[i]=*address(v,a+i);
}
void rv_write_bytes(RV *v,uint32_t a,const uint8_t *in,uint32_t n){
#ifdef RV_OBJECT_BACKEND
    if(v->pool){ro_store(v->pool,&v->space,a,in,n);return;}
#endif
    uint8_t *out=rv_buffer(v,a,n,1);for(uint32_t i=0;i<n;i++)out[i]=in[i];
}
unsigned rv_fork_memory(RV *dst,uint8_t *ram,RV *src){
#ifdef RV_OBJECT_BACKEND
    if(src->pool){ROSpace space={0};if(ro_fork(src->pool,&space,&src->space))return UINT32_MAX;
        for(unsigned j=0;j<sizeof(RV);j++)((volatile uint8_t *)dst)[j]=((const uint8_t *)src)[j];
        for(unsigned j=0;j<sizeof(space);j++)((volatile uint8_t *)&dst->space)[j]=((const uint8_t *)&space)[j];
        unsigned shared=0;for(unsigned i=0;i<RO_VPAGES;i++)shared+=space.mapped[i];return shared;}
#endif
    /* Scheduler guarantees two distinct live slots and no existing peer. */
    if(src==dst||src->peer||ram==src->mem)return 0;
    for(unsigned j=0;j<sizeof(RV);j++)((volatile uint8_t *)dst)[j]=((const uint8_t *)src)[j];
    dst->mem=ram;dst->peer=src;src->peer=dst;dst->cow_copies=0;
    unsigned shared=0;for(unsigned p=0;p<RV_SIZE/RV_PAGE;p++){dst->borrowed[p]=(uint8_t)!!src->pages[p];shared+=dst->borrowed[p];}
    return shared;
}
void rv_release_memory(RV *v){
#ifdef RV_OBJECT_BACKEND
    if(v->pool){ro_drop(v->pool,&v->space);v->pool=0;return;}
#endif
    if(!v->peer)return;
    RV *other=v->peer;
    for(unsigned p=0;p<RV_SIZE/RV_PAGE;p++){private_page(other,p);v->borrowed[p]=0;}
    other->peer=0;v->peer=0;
}
static int load_image(RV *v,uint8_t *mem,const uint8_t *f,size_t len,int argc,const char *const *argv,int envc,const char *const *envp){
    if(len<52||get(f,4)!=0x464c457f||f[4]!=1||f[5]!=1||f[6]!=1||get(f+16,2)!=2||get(f+18,2)!=243||get(f+20,4)!=1||get(f+36,4)!=0||get(f+40,2)!=52||get(f+42,2)!=32||argc<0||argc>64||envc<0||envc>64)return -1;
    uint32_t off=get(f+28,4),pn=get(f+44,2),end=RV_PAGE,phdr=0;
    if(off>len||pn>(len-off)/32||!pn)return -1;
    zero((uint8_t*)v,sizeof(*v));if(mem)zero(mem,RV_SIZE);v->mem=mem;
    for(uint32_t i=0;i<pn;i++){
        const uint8_t *p=f+off+32*i;uint32_t type=get(p,4);if(type==2||type==3||type==7)return -1;if(type!=1)continue;
        uint32_t o=get(p+4,4),a=get(p+8,4),fs=get(p+16,4),ms=get(p+20,4),fl=get(p+24,4),align=get(p+28,4);
        if(o>len||fs>len-o||fs>ms||a<RV_PAGE||a>RV_STACK||ms>RV_STACK-a||!fl||fl>7||((fl&3)==3)|| (align>1&&((align&(align-1))||((a^o)&(align-1)))))return -1;
        if(!ms)continue;
        unsigned perm=((fl&4)?RV_R:0)|((fl&2)?RV_W:0)|((fl&1)?RV_X:0);
        for(uint32_t j=a/RV_PAGE;j<=(a+ms-1)/RV_PAGE;j++){if(v->pages[j])return -1;v->pages[j]=(uint8_t)perm;}
        if(mem)for(uint32_t j=0;j<fs;j++)mem[a+j]=f[o+j];
        if(a+ms>end)end=a+ms;
        if((perm&RV_R)&&off>=o&&off-o<=fs&&pn*32<=fs-(off-o))phdr=a+off-o;
    }
    v->pc=get(f+24,4);if((v->pc&3)||!access(v,v->pc,4,RV_X))return -1;
    v->heap=v->brk=(end+RV_PAGE-1)&~(RV_PAGE-1);
    for(uint32_t j=RV_STACK/RV_PAGE;j<RV_SIZE/RV_PAGE;j++)v->pages[j]=RV_R|RV_W;
    uint32_t sp=RV_SIZE,ptrs[128];
    for(int i=argc+envc-1;i>=0;i--){const char *s=i<argc?argv[i]:envp[i-argc];size_t n=0;while(n<4096&&s[n])n++;if(n==4096||n+1>sp-RV_STACK)return -1;sp-=(uint32_t)n+1;if(mem)for(size_t j=0;j<=n;j++)mem[sp+j]=(uint8_t)s[j];ptrs[i]=sp;}
    /* Only publish AT_PHDR if the actual program headers are mapped. No fake entropy. */
    uint32_t aux[18],an=0;
    if(phdr){aux[an++]=3;aux[an++]=phdr;aux[an++]=4;aux[an++]=32;aux[an++]=5;aux[an++]=pn;}
    aux[an++]=6;aux[an++]=RV_PAGE;aux[an++]=7;aux[an++]=0;aux[an++]=9;aux[an++]=v->pc;
    if(argc){aux[an++]=31;aux[an++]=ptrs[0];}
    aux[an++]=0;aux[an++]=0;
    uint32_t bytes=4u*((uint32_t)(argc+envc)+3u+an);if(bytes>sp-RV_STACK)return -1;sp=(sp-bytes)&~15u;if(sp<RV_STACK)return -1;
    if(mem){uint32_t at=sp;put(mem+at,4,(uint32_t)argc);at+=4;
    for(int i=0;i<argc;i++){put(mem+at,4,ptrs[i]);at+=4;}put(mem+at,4,0);at+=4;
    for(int i=0;i<envc;i++){put(mem+at,4,ptrs[argc+i]);at+=4;}put(mem+at,4,0);at+=4;
    for(uint32_t i=0;i<an;i++){put(mem+at,4,aux[i]);at+=4;}}v->r[2]=sp;return 0;
}
/* Source image and argument strings must be immutable and disjoint from destination RAM. */
int rv_load_env(RV *v,uint8_t *mem,const uint8_t *f,size_t len,int argc,const char *const *argv,int envc,const char *const *envp){
    RV candidate;if(!v||!mem||!f||load_image(&candidate,0,f,len,argc,argv,envc,envp))return -1;
    return load_image(v,mem,f,len,argc,argv,envc,envp);
}
#ifdef RV_OBJECT_BACKEND
/* One shared scratch region for loader and synchronous I/O; no persistent flat image. */
int rv_load_pool(RV *v,ROPool *pool,uint8_t *scratch,const uint8_t *f,size_t len,int argc,const char *const *argv,int envc,const char *const *envp){
    RV candidate;if(!f||load_image(&candidate,0,f,len,argc,argv,envc,envp))return -1;
    unsigned count=0,old=0;for(unsigned i=0;i<RO_VPAGES;i++){count+=!!candidate.pages[i];if(v->pool==pool)old+=v->space.mapped[i];}
    if(count>RO_OBJECTS-pool->reserved+old)return -1;
    if(load_image(&candidate,scratch,f,len,argc,argv,envc,envp))return -1;
    rv_release_memory(v);
    for(unsigned j=0;j<sizeof(RV);j++)((volatile uint8_t *)v)[j]=((const uint8_t *)&candidate)[j];
    v->pool=pool;
    for(unsigned i=0;i<RO_VPAGES;i++)if(v->pages[i]){ro_map(pool,&v->space,i,1);ro_write(pool,&v->space,i*RO_PAGE,scratch+i*RO_PAGE,RO_PAGE);}
    return 0;
}
#endif
/* Validate before detaching; rejected exec preserves the live representation too. */
int rv_replace_env(RV *v,const uint8_t *f,size_t len,int argc,const char *const *argv,int envc,const char *const *envp){
#ifdef RV_OBJECT_BACKEND
    if(v->pool)return rv_load_pool(v,v->pool,v->mem,f,len,argc,argv,envc,envp);
#endif
    RV candidate;if(!f||load_image(&candidate,0,f,len,argc,argv,envc,envp))return -1;
    rv_release_memory(v);uint32_t copies=v->cow_copies;uint8_t *ram=v->mem;
    int r=load_image(v,ram,f,len,argc,argv,envc,envp);v->cow_copies=copies;return r;
}
int rv_load(RV *v,uint8_t *mem,const uint8_t *f,size_t len,int argc,const char *const *argv){return rv_load_env(v,mem,f,len,argc,argv,0,0);}
/* Anonymous private mappings use a distinct allocation bit so PROT_NONE stays reserved. */
static int32_t vm_map(RV *v,uint32_t hint,uint32_t size,uint32_t prot,uint32_t flags,uint32_t fd,uint32_t offset){
    if(!size||size>RV_STACK||prot>7||(prot&6)==6||flags!=0x22||fd!=~0u||offset)return -22;
    (void)hint; /* non-fixed hint is advisory */
    uint32_t count=(size+RV_PAGE-1)/RV_PAGE,low=(v->brk+RV_PAGE-1)/RV_PAGE,run=0;
    for(uint32_t p=RV_STACK/RV_PAGE;p>low;){p--;if(v->pages[p])run=0;else if(++run==count){
#ifdef RV_OBJECT_BACKEND
        if(v->pool&&ro_map(v->pool,&v->space,p,count))return -12;
#endif
        for(uint32_t j=p;j<p+count;j++){
#ifdef RV_OBJECT_BACKEND
            if(!v->pool)
#endif
            zero(rv_buffer(v,j*RV_PAGE,RV_PAGE,1),RV_PAGE);
v->pages[j]=(uint8_t)(RV_MAP|prot);}return (int32_t)(p*RV_PAGE);}}
    return -12;
}
static int32_t vm_change(RV *v,uint32_t addr,uint32_t size,uint32_t prot,int unmap){
    if(!size||addr%RV_PAGE||addr>=RV_STACK||size>RV_STACK-addr||prot>7||(prot&6)==6)return -22;
    uint32_t first=addr/RV_PAGE,last=(addr+size-1)/RV_PAGE;
    for(uint32_t p=first;p<=last;p++)if(!(v->pages[p]&RV_MAP))return -12;
#ifdef RV_OBJECT_BACKEND
    if(unmap&&v->pool)ro_unmap(v->pool,&v->space,first,last-first+1);
#endif
    for(uint32_t p=first;p<=last;p++){v->pages[p]=unmap?0:(uint8_t)(RV_MAP|prot);if(unmap)v->borrowed[p]=0;}
    return 0;
}
static uint32_t sra(uint32_t a,unsigned b){return b?(a>>b)|((a&0x80000000u)?(~0u<<(32-b)):0):a;}
static int slt(uint32_t a,uint32_t b){return (a^0x80000000u)<(b^0x80000000u);}
static int name_at(RV *v,uint32_t a,char *name){for(unsigned i=0;i<FS_NAME;i++){if(!access(v,a,1,RV_R))return -14;name[i]=(char)rv_word(v,a++,1);if(!name[i])return 0;}return -36;}
static int32_t syscall(RV *v,rv_io io,void *ctx,RVFS *fs,RVFds *fds){uint32_t n=v->r[17],a=v->r[10],b=v->r[11],c=v->r[12];
    if(n==93||n==94){v->halted=1;v->status=a&255;return 0;}
    if(n==56||n==35){if(a!=(uint32_t)-100)return -22;if(n==35&&c)return -22;char name[FS_NAME];int r=name_at(v,b,name);if(r)return r;return n==56?fs_open(fs,fds,name,c):fs_unlink(fs,name);}
    if(n==57)return fs_close(fs,fds,a);
    if(n==62){uint32_t ptr=v->r[13];if(!access(v,ptr,8,RV_W))return -14;int32_t r=fs_seek(fs,fds,a,b,c,v->r[14]);if(r<0)return r;uint8_t out[8];put(out,4,(uint32_t)r);put(out+4,4,0);rv_write_bytes(v,ptr,out,8);return 0;}
    if(n==23||n==24)return fs_dup(fs,fds,a,n==23?0:b,n==23?0:c,n==24);
    if(n==25)return fs_fcntl(fs,fds,a,b,c);
    if(n==291){char name[FS_NAME];uint32_t ptr=v->r[14];if(!access(v,ptr,256,RV_W))return -14;int r=name_at(v,b,name);if(r)return r;uint8_t out[256];r=fs_statx(fs,fds,a,name,c,out);if(!r)rv_write_bytes(v,ptr,out,256);return r;}
    if(n==63||n==64){int stream;int r=fs_access(fs,fds,a,n==64,&stream);if(r)return r;
        if(!access(v,b,c,n==63?RV_W:RV_R))return -14;
        if(stream<0&&!fs_ready(fs,fds,a,n==64,c))return FS_BLOCK;
#ifdef RV_OBJECT_BACKEND
        if(v->pool){uint8_t *buf=v->mem;if(n==64)rv_read_bytes(v,b,buf,c);
            int32_t result=stream>=0?(io?io(ctx,n==64,(uint32_t)stream,buf,c):-38):(n==63?fs_read(fs,fds,a,buf,c):fs_write(fs,fds,a,buf,c));
            if(n==63&&result>0&&(uint32_t)result<=c)rv_write_bytes(v,b,buf,(uint32_t)result);
            return result;}
#endif
        uint8_t *buf=rv_buffer(v,b,c,n==63);
        if(stream>=0)return io?io(ctx,n==64,(uint32_t)stream,buf,c):-38;
        return n==63?fs_read(fs,fds,a,buf,c):fs_write(fs,fds,a,buf,c); }
    if(n==222)return vm_map(v,a,b,c,v->r[13],v->r[14],v->r[15]);
    if(n==215||n==226)return vm_change(v,a,b,n==215?0:c,n==215);
    if(n==214){if(a>=v->heap&&a<=RV_STACK){uint32_t old=(v->brk+RV_PAGE-1)/RV_PAGE,now=(a+RV_PAGE-1)/RV_PAGE;for(uint32_t p=old;p<now;p++)if(v->pages[p])return (int32_t)v->brk;
#ifdef RV_OBJECT_BACKEND
        if(v->pool){if(now>old&&ro_map(v->pool,&v->space,old,now-old))return (int32_t)v->brk;if(now<old)ro_unmap(v->pool,&v->space,now,old-now);}
#endif
        for(uint32_t p=old;p<now;p++){
#ifdef RV_OBJECT_BACKEND
            if(!v->pool)
#endif
            zero(rv_buffer(v,p*RV_PAGE,RV_PAGE,1),RV_PAGE);
v->pages[p]=RV_R|RV_W;}for(uint32_t p=now;p<old;p++){v->pages[p]=0;v->borrowed[p]=0;}v->brk=a;}return (int32_t)v->brk;}
    return -38;
}
int rv_run(RV *v,uint32_t budget,rv_io io,void *ctx,RVFS *fs,RVFds *fds){
    while(!v->halted&&budget--){uint32_t pc=v->pc;if((pc&3)||!access(v,pc,4,RV_X))return -2;
        uint32_t i=rv_word(v,pc,4),op=i&127,d=(i>>7)&31,f=(i>>12)&7,s=(i>>15)&31,t=(i>>20)&31,h=i>>25,a=v->r[s],b=v->r[t],z=0,next=pc+4,imm=sx(i>>20,12);int wr=1;
        switch(op){
        case 0x37:z=i&0xfffff000u;break;case 0x17:z=pc+(i&0xfffff000u);break;
        case 0x6f:z=next;next=pc+sx(((i>>31)<<20)|(((i>>12)&255)<<12)|(((i>>20)&1)<<11)|(((i>>21)&1023)<<1),21);break;
        case 0x67:if(f)return -3;z=next;next=(a+imm)&~1u;break;
        case 0x63:{int take;switch(f){case 0:take=a==b;break;case 1:take=a!=b;break;case 4:take=slt(a,b);break;case 5:take=!slt(a,b);break;case 6:take=a<b;break;case 7:take=a>=b;break;default:return -3;}if(take)next=pc+sx(((i>>31)<<12)|(((i>>7)&1)<<11)|(((i>>25)&63)<<5)|(((i>>8)&15)<<1),13);wr=0;break;}
        case 3:{unsigned n;if(f==0||f==4)n=1;else if(f==1||f==5)n=2;else if(f==2)n=4;else return -3;uint32_t addr=a+imm;if((addr&(n-1))||!access(v,addr,n,RV_R))return -4;z=rv_word(v,addr,n);if(f<2)z=sx(z,n*8);break;}
        case 0x23:{if(f>2)return -3;unsigned n=1u<<f;uint32_t addr=a+sx((h<<5)|d,12);if((addr&(n-1))||!access(v,addr,n,RV_W))return -4;uint8_t buf[4];put(buf,n,b);rv_write_bytes(v,addr,buf,n);wr=0;break;}
        case 0x13:switch(f){case 0:z=a+imm;break;case 2:z=slt(a,imm);break;case 3:z=a<imm;break;case 4:z=a^imm;break;case 6:z=a|imm;break;case 7:z=a&imm;break;case 1:if(h)return -3;z=a<<t;break;case 5:if(h!=0&&h!=32)return -3;z=h?sra(a,t):a>>t;break;}break;
        case 0x33:if(h==1){switch(f){case 0:z=a*b;break;case 1:z=(uint32_t)((uint64_t)((int64_t)(int32_t)a*(int64_t)(int32_t)b)>>32);break;case 2:z=(uint32_t)((uint64_t)((int64_t)(int32_t)a*(int64_t)b)>>32);break;case 3:z=(uint32_t)(((uint64_t)a*b)>>32);break;case 4:z=!b?~0u:(a==0x80000000u&&b==~0u)?a:(uint32_t)((int32_t)a/(int32_t)b);break;case 5:z=b?a/b:~0u;break;case 6:z=!b?a:(a==0x80000000u&&b==~0u)?0:(uint32_t)((int32_t)a%(int32_t)b);break;case 7:z=b?a%b:a;break;}}else {if(h&&!(h==32&&(f==0||f==5)))return -3;switch(f){case 0:z=h?a-b:a+b;break;case 1:z=a<<(b&31);break;case 2:z=slt(a,b);break;case 3:z=a<b;break;case 4:z=a^b;break;case 5:z=h?sra(a,b&31):a>>(b&31);break;case 6:z=a|b;break;case 7:z=a&b;break;}}break;
        case 0x0f:if(f!=0)return -3;wr=0;break;
        case 0x73:if(i!=0x73)return -3;if(v->process_calls&&(v->r[17]==59||v->r[17]==172||v->r[17]==220||v->r[17]==221||v->r[17]==260))return 3;z=(uint32_t)syscall(v,io,ctx,fs,fds);if(z==(uint32_t)FS_BLOCK&&(v->r[17]==63||v->r[17]==64)){int stream;if(!fs_access(fs,fds,v->r[10],v->r[17]==64,&stream)&&stream<0)return 2;}d=10;break;
        default:return -3;
        }
        if(next&3)return -2;
        if(wr&&d)v->r[d]=z;
        v->pc=next;v->steps++;
    }return v->halted?0:1;
}
