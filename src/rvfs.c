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
int32_t fs_close(RVFS *fs,RVFds *t,uint32_t n){RVOpen *d=fd(fs,t,n);if(!d)return -9;d->refs--;t->slots[n]=0;t->cloexec[n]=0;return 0;}
void fs_drop_fds(RVFS *fs,RVFds *t){for(unsigned i=0;i<FS_FDS;i++)if(t->slots[i])fs_close(fs,t,i);}
void fs_reset_fds(RVFS *fs,RVFds *t){fs_drop_fds(fs,t);for(unsigned i=0;i<3;i++){unsigned j=free_open(fs);if(j==FS_OPEN)break;fs->opens[j]=(RVOpen){i,0,i?1u:0u,0,1};attach(fs,t,i,j,0);}}
int32_t fs_open(RVFS *fs,RVFds *t,const char *name,uint32_t flags){
    if(!fs_name(name))return -22;
    if((flags&3)==3||(flags&~(3u|CREATE|EXCL|TRUNC|APPEND|00100000u|CLOEXEC))||((flags&TRUNC)&&!(flags&3)))return -22;
    int i=find(fs,name);if(i>=0&&(flags&CREATE)&&(flags&EXCL))return -17;if(i<0&&!(flags&CREATE))return -2;
    unsigned slot=free_slot(t,0),j=free_open(fs);if(slot==FS_FDS)return -24;if(j==FS_OPEN)return -23;
    if(i<0){for(i=0;i<(int)FS_FILES&&fs->files[i].name[0];i++){}if(i==(int)FS_FILES)return -28;RVFile *f=&fs->files[i];unsigned k=0;do{f->name[k]=name[k];}while(name[k++]);f->size=0;}
    if(flags&TRUNC)fs->files[i].size=0;
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
int32_t fs_access(RVFS *fs,RVFds *t,uint32_t n,int output,int *stream){RVOpen *d=fd(fs,t,n);if(!d||(output?!(d->flags&3):(d->flags&3)==1))return -9;*stream=d->stream?(int)d->object:-1;return 0;}
int32_t fs_read(RVFS *fs,RVFds *t,uint32_t n,uint8_t *buf,uint32_t count){RVOpen *d=fd(fs,t,n);if(!d||d->stream||(d->flags&3)==1)return -9;RVFile *f=&fs->files[d->object];if(d->pos>=f->size)return 0;uint32_t avail=f->size-d->pos;if(count>avail)count=avail;for(uint32_t i=0;i<count;i++)buf[i]=f->data[d->pos+i];d->pos+=count;return (int32_t)count;}
int32_t fs_write(RVFS *fs,RVFds *t,uint32_t n,const uint8_t *buf,uint32_t count){RVOpen *d=fd(fs,t,n);if(!d||d->stream||!(d->flags&3))return -9;if(!count)return 0;RVFile *f=&fs->files[d->object];uint32_t pos=(d->flags&APPEND)?f->size:d->pos;if(count>FS_CAP-pos)return -28;for(uint32_t i=f->size;i<pos;i++)f->data[i]=0;for(uint32_t i=0;i<count;i++)f->data[pos+i]=buf[i];d->pos=pos+count;if(d->pos>f->size)f->size=d->pos;return (int32_t)count;}
int32_t fs_seek(RVFS *fs,RVFds *t,uint32_t n,uint32_t hi,uint32_t lo,uint32_t whence){RVOpen *d=fd(fs,t,n);if(!d)return -9;if(d->stream)return -29;uint32_t base;if(whence==0)base=0;else if(whence==1)base=d->pos;else if(whence==2)base=fs->files[d->object].size;else return -22;
    if(hi==0){if(lo>FS_CAP-base)return -22;d->pos=base+lo;}else if(hi==0xffffffffu&&lo){uint32_t neg=0u-lo;if(neg>base)return -22;d->pos=base-neg;}else return -22;return (int32_t)d->pos;}
int32_t fs_unlink(RVFS *fs,const char *name){if(!fs_name(name))return -22;int i=find(fs,name);if(i<0)return -2;for(unsigned j=0;j<FS_OPEN;j++)if(fs->opens[j].refs&&!fs->opens[j].stream&&fs->opens[j].object==(uint32_t)i)return -16;fs->files[i].name[0]=0;fs->files[i].size=0;return 0;}
static void put(uint8_t *p,unsigned n,uint32_t x){for(unsigned i=0;i<n;i++)p[i]=(uint8_t)(x>>(8*i));}
/* Linux statx 256-byte wire structure, only fields we can actually describe. */
int32_t fs_statx(RVFS *fs,RVFds *t,uint32_t dir,const char *name,uint32_t flags,uint8_t *out){
    int i=-1,stream=0;uint32_t size=0;if(flags&~0x1000u)return -22;
    if(!*name&&(flags&0x1000u)){RVOpen *d=fd(fs,t,dir);if(!d)return -9;i=(int)d->object;stream=d->stream;}
    else{if(dir!=(uint32_t)-100||!fs_name(name))return -22;i=find(fs,name);if(i<0)return -2;}
    if(!stream)size=fs->files[i].size;
    for(unsigned j=0;j<256;j++)out[j]=0;
    put(out,4,0x707u);put(out+4,4,4096);put(out+16,4,1);put(out+28,2,stream?0020666u:0100666u);put(out+32,4,(uint32_t)i+1+(stream?FS_FILES:0));put(out+40,4,size);put(out+48,4,(size+511)/512);return 0;
}
