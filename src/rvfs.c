#include "rvfs.h"
#define CREATE 0100u
#define EXCL 0200u
#define TRUNC 01000u
#define APPEND 02000u
#define CLOEXEC 02000000u
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
int fs_name(const char *s){unsigned n=0;for(;n<FS_NAME&&s[n];n++){unsigned c=(unsigned char)s[n];if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))return 0;}return n&&n<FS_NAME&&!eq(s,".")&&!eq(s,"..");}
static int find(RVFS *fs,const char *name){for(unsigned i=0;i<FS_FILES;i++)if(fs->files[i].name[0]&&eq(fs->files[i].name,name))return (int)i;return -1;}
static RVOpen *fd(RVFS *fs,RVFds *t,uint32_t n){return n<FS_FDS&&t->slots[n]?&fs->opens[t->slots[n]-1]:0;}
static unsigned free_slot(RVFds *t,unsigned start){while(start<FS_FDS&&t->slots[start])start++;return start;}
static unsigned free_open(RVFS *fs){unsigned j=0;while(j<FS_OPEN&&fs->opens[j].refs)j++;return j;}
static void attach(RVFS *fs,RVFds *t,unsigned slot,unsigned obj,unsigned clo){t->slots[slot]=(uint8_t)(obj+1);t->cloexec[slot]=(uint8_t)clo;fs->opens[obj].refs++;}
int32_t fs_close(RVFS *fs,RVFds *t,uint32_t n){RVOpen *d=fd(fs,t,n);if(!d)return -9;if(!--d->refs&&d->stream>=2){RVPipe *p=&fs->pipes[d->object];if(d->stream==2)p->readers--;else p->writers--;if(!p->readers&&!p->writers)p->size=p->head=0;}t->slots[n]=0;t->cloexec[n]=0;return 0;}
void fs_drop_fds(RVFS *fs,RVFds *t){for(unsigned i=0;i<FS_FDS;i++)if(t->slots[i])fs_close(fs,t,i);}
void fs_reset_fds(RVFS *fs,RVFds *t){fs_drop_fds(fs,t);for(unsigned i=0;i<3;i++){unsigned j=free_open(fs);if(j==FS_OPEN)break;fs->opens[j]=(RVOpen){i,0,i?1u:0u,0,1};attach(fs,t,i,j,0);}}
int32_t fs_open(RVFS *fs,RVFds *t,const char *name,uint32_t flags){
    if(!fs_name(name))return -22;
    if((flags&3)==3||(flags&~(3u|CREATE|EXCL|TRUNC|APPEND|00100000u|CLOEXEC))||((flags&TRUNC)&&!(flags&3)))return -22;
    int i=find(fs,name);if(i>=0&&(flags&CREATE)&&(flags&EXCL))return -17;if(i<0&&!(flags&CREATE))return -2;
    unsigned slot=free_slot(t,0),j=free_open(fs);if(slot==FS_FDS)return -24;if(j==FS_OPEN)return -23;
    if(i<0){for(i=0;i<(int)FS_FILES&&fs->files[i].name[0];i++){}if(i==(int)FS_FILES)return -28;RVFile *f=&fs->files[i];unsigned k=0;do{f->name[k]=name[k];}while(name[k++]);f->size=0;}
    if(flags&TRUNC)fs_file_clear(fs,&fs->files[i]);
    fs->opens[j]=(RVOpen){(uint32_t)i,0,flags&(3u|APPEND|00100000u),0,0};attach(fs,t,slot,j,!!(flags&CLOEXEC));return (int32_t)slot;
}
int32_t fs_dup(RVFS *fs,RVFds *t,uint32_t old,uint32_t target,uint32_t flags,int exact){
    if(!fd(fs,t,old))return -9;
    if(flags&~CLOEXEC)return -22;
    if(exact){if(old==target)return -22;if(target>=FS_FDS)return -9;}else{if(target>=FS_FDS)return -22;target=free_slot(t,target);if(target==FS_FDS)return -24;}
    unsigned obj=t->slots[old]-1;if(t->slots[target])fs_close(fs,t,target);attach(fs,t,target,obj,!!flags);return (int32_t)target;
}
int32_t fs_fcntl(RVFS *fs,RVFds *t,uint32_t n,uint32_t cmd,uint32_t arg){RVOpen *d=fd(fs,t,n);if(!d)return -9;
    switch(cmd){case 0:return fs_dup(fs,t,n,arg,0,0);case 1030:return fs_dup(fs,t,n,arg,CLOEXEC,0);case 1:return t->cloexec[n];case 2:t->cloexec[n]=(uint8_t)(arg&1);return 0;case 3:return (int32_t)d->flags;case 4:if(arg&~(3u|APPEND|00100000u))return -22;d->flags=(d->flags&~APPEND)|(arg&APPEND);return 0;default:return -22;}}
int32_t fs_access(RVFS *fs,RVFds *t,uint32_t n,int output,int *stream){RVOpen *d=fd(fs,t,n);if(!d||(output?!(d->flags&3):(d->flags&3)==1))return -9;*stream=d->stream==1?(int)d->object:-1;return 0;}
void fs_file_clear(RVFS *fs,RVFile *f){for(unsigned i=0;i<FS_PAGES;i++)page_clear(&fs->pool,&f->pages[i]);f->size=0;}
int32_t fs_file_read(const RVFS *fs,const RVFile *f,uint32_t pos,uint8_t *buf,uint32_t count){
    if(pos>=f->size)return 0;
    if(count>f->size-pos)count=f->size-pos;
    for(uint32_t i=0;i<count;i++){uint32_t at=pos+i;buf[i]=page_byte(&fs->pool,&f->pages[at/FS_PAGE],at%FS_PAGE);}return (int32_t)count;
}
int32_t fs_file_write(RVFS *fs,RVFile *f,uint32_t pos,const uint8_t *buf,uint32_t count){
    if(pos>FS_CAP||count>FS_CAP-pos)return -28;
    if(!count)return 0;
    uint8_t page[FS_PAGE];uint32_t done=0;
    while(done<count){uint32_t at=pos+done,off=at%FS_PAGE,n=FS_PAGE-off;if(n>count-done)n=count-done;RVPage *p=&f->pages[at/FS_PAGE];
        if(off==0&&n==FS_PAGE)page_assign(&fs->pool,p,buf+done);
        else {for(unsigned i=0;i<FS_PAGE;i++)page[i]=page_byte(&fs->pool,p,i);for(unsigned i=0;i<n;i++)page[off+i]=buf[done+i];page_assign(&fs->pool,p,page);}done+=n;}
    if(pos+count>f->size)f->size=pos+count;
    return (int32_t)count;
}
int32_t fs_read(RVFS *fs,RVFds *t,uint32_t n,uint8_t *buf,uint32_t count){RVOpen *d=fd(fs,t,n);if(!d||(d->flags&3)==1||d->stream==1)return -9;if(d->stream==2){RVPipe *p=&fs->pipes[d->object];if(!count)return 0;if(!p->size)return p->writers?FS_BLOCK:0;if(count>p->size)count=p->size;for(uint32_t i=0;i<count;i++)buf[i]=p->data[(p->head+i)%FS_PIPE_CAP];p->head=(p->head+count)%FS_PIPE_CAP;p->size-=count;return (int32_t)count;}int32_t r=fs_file_read(fs,&fs->files[d->object],d->pos,buf,count);if(r>0)d->pos+=(uint32_t)r;return r;}
int32_t fs_write(RVFS *fs,RVFds *t,uint32_t n,const uint8_t *buf,uint32_t count){RVOpen *d=fd(fs,t,n);if(!d||d->stream==1||!(d->flags&3))return -9;if(!count)return 0;if(d->stream==3){RVPipe *p=&fs->pipes[d->object];if(!p->readers)return -32;uint32_t space=FS_PIPE_CAP-p->size;if(!space||(count<=FS_PIPE_CAP&&count>space))return FS_BLOCK;if(count>space)count=space;for(uint32_t i=0;i<count;i++)p->data[(p->head+p->size+i)%FS_PIPE_CAP]=buf[i];p->size+=count;return (int32_t)count;}RVFile *f=&fs->files[d->object];uint32_t pos=(d->flags&APPEND)?f->size:d->pos;int32_t r=fs_file_write(fs,f,pos,buf,count);if(r>0)d->pos=pos+(uint32_t)r;return r;}
int32_t fs_seek(RVFS *fs,RVFds *t,uint32_t n,uint32_t hi,uint32_t lo,uint32_t whence){RVOpen *d=fd(fs,t,n);if(!d)return -9;if(d->stream)return -29;uint32_t base;if(whence==0)base=0;else if(whence==1)base=d->pos;else if(whence==2)base=fs->files[d->object].size;else return -22;
    if(hi==0){if(lo>FS_CAP-base)return -22;d->pos=base+lo;}else if(hi==0xffffffffu&&lo){uint32_t neg=0u-lo;if(neg>base)return -22;d->pos=base-neg;}else return -22;return (int32_t)d->pos;}
int32_t fs_unlink(RVFS *fs,const char *name){if(!fs_name(name))return -22;int i=find(fs,name);if(i<0)return -2;for(unsigned j=0;j<FS_OPEN;j++)if(fs->opens[j].refs&&!fs->opens[j].stream&&fs->opens[j].object==(uint32_t)i)return -16;fs->files[i].name[0]=0;fs_file_clear(fs,&fs->files[i]);return 0;}
static void put(uint8_t *p,unsigned n,uint32_t x){for(unsigned i=0;i<n;i++)p[i]=(uint8_t)(x>>(8*i));}
/* Linux statx 256-byte wire structure, only fields we can actually describe. */
int32_t fs_statx(RVFS *fs,RVFds *t,uint32_t dir,const char *name,uint32_t flags,uint8_t *out){
    int i=-1,stream=0;uint32_t size=0;if(flags&~0x1000u)return -22;
    if(!*name&&(flags&0x1000u)){RVOpen *d=fd(fs,t,dir);if(!d)return -9;i=(int)d->object;stream=d->stream;}
    else{if(dir!=(uint32_t)-100||!fs_name(name))return -22;i=find(fs,name);if(i<0)return -2;}
    if(!stream)size=fs->files[i].size;
    for(unsigned j=0;j<256;j++)out[j]=0;
    put(out,4,0x707u);put(out+4,4,4096);put(out+16,4,1);put(out+28,2,stream>=2?0010600u:stream?0020666u:0100666u);put(out+32,4,(uint32_t)i+1+(stream>=2?FS_FILES+3:stream?FS_FILES:0));put(out+40,4,size);put(out+48,4,(size+511)/512);return 0;
}

/* Trusted connection: install read and write endpoints at empty local slots. */
int fs_pipe(RVFS *fs,RVFds *reader,RVFds *writer,uint32_t rd,uint32_t wr){
    if(rd>=FS_FDS||wr>=FS_FDS||reader->slots[rd]||writer->slots[wr]||(reader==writer&&rd==wr))return -22;
    unsigned p=0,a=FS_OPEN,b=FS_OPEN;while(p<FS_PIPES&&(fs->pipes[p].readers||fs->pipes[p].writers))p++;
    for(unsigned j=0;j<FS_OPEN;j++)if(!fs->opens[j].refs){if(a==FS_OPEN)a=j;else{b=j;break;}}
    if(p==FS_PIPES||b==FS_OPEN)return -23;
    fs->pipes[p].head=fs->pipes[p].size=0;fs->pipes[p].readers=fs->pipes[p].writers=1;
    fs->opens[a]=(RVOpen){p,0,0,0,2};fs->opens[b]=(RVOpen){p,0,1,0,3};attach(fs,reader,rd,a,0);attach(fs,writer,wr,b,0);return 0;
}
/* A terminal error or EOF is also a realizable continuation. */
int fs_ready(RVFS *fs,RVFds *t,uint32_t n,int output,uint32_t count){
    RVOpen *d=fd(fs,t,n);if(!d||!count||d->stream<2)return 1;
    RVPipe *p=&fs->pipes[d->object];
    if(!output)return p->size||!p->writers;
    uint32_t space=FS_PIPE_CAP-p->size;return !p->readers||(count<=FS_PIPE_CAP?space>=count:space!=0);
}
