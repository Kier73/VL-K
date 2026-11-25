#include "rvfs.h"
#define CREATE 0100u
#define EXCL 0200u
#define TRUNC 01000u
#define APPEND 02000u
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
int fs_name(const char *s){unsigned n=0;for(;n<FS_NAME&&s[n];n++){unsigned c=(unsigned char)s[n];if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))return 0;}return n&&n<FS_NAME&&!eq(s,".")&&!eq(s,"..");}
void fs_reset_fds(RVFS *fs){for(unsigned i=0;i<FS_FDS;i++)fs->fds[i].used=0;fs->stdio=7;}
static int find(RVFS *fs,const char *name){for(unsigned i=0;i<FS_FILES;i++)if(fs->files[i].name[0]&&eq(fs->files[i].name,name))return (int)i;return -1;}
static RVFd *fd(RVFS *fs,uint32_t n){return n>=3&&n-3<FS_FDS&&fs->fds[n-3].used?&fs->fds[n-3]:0;}
int32_t fs_open(RVFS *fs,const char *name,uint32_t flags){
    if(!fs_name(name))return -22;
    if((flags&3)==3||(flags&~(3u|CREATE|EXCL|TRUNC|APPEND|00100000u|02000000u))||((flags&TRUNC)&&!(flags&3)))return -22;
    int i=find(fs,name);if(i>=0&&(flags&CREATE)&&(flags&EXCL))return -17;if(i<0&&!(flags&CREATE))return -2;
    unsigned j=0;while(j<FS_FDS&&fs->fds[j].used)j++;if(j==FS_FDS)return -24;
    if(i<0){for(i=0;i<(int)FS_FILES&&fs->files[i].name[0];i++){}if(i==(int)FS_FILES)return -28;RVFile *f=&fs->files[i];unsigned k=0;do{f->name[k]=name[k];}while(name[k++]);f->size=0;}
    if(flags&TRUNC)fs->files[i].size=0;
    RVFd *d=&fs->fds[j];d->used=1;d->file=(uint32_t)i;d->pos=0;d->flags=flags;return (int32_t)j+3;
}
int32_t fs_close(RVFS *fs,uint32_t n){if(n<3){if(!(fs->stdio&(1u<<n)))return -9;fs->stdio&=~(1u<<n);return 0;}RVFd *d=fd(fs,n);if(!d)return -9;d->used=0;return 0;}
int32_t fs_read(RVFS *fs,uint32_t n,uint8_t *buf,uint32_t count){RVFd *d=fd(fs,n);if(!d||(d->flags&3)==1)return -9;RVFile *f=&fs->files[d->file];if(d->pos>=f->size)return 0;uint32_t avail=f->size-d->pos;if(count>avail)count=avail;for(uint32_t i=0;i<count;i++)buf[i]=f->data[d->pos+i];d->pos+=count;return (int32_t)count;}
int32_t fs_write(RVFS *fs,uint32_t n,const uint8_t *buf,uint32_t count){RVFd *d=fd(fs,n);if(!d||!(d->flags&3))return -9;if(!count)return 0;RVFile *f=&fs->files[d->file];uint32_t pos=(d->flags&APPEND)?f->size:d->pos;if(count>FS_CAP-pos)return -28;for(uint32_t i=f->size;i<pos;i++)f->data[i]=0;for(uint32_t i=0;i<count;i++)f->data[pos+i]=buf[i];d->pos=pos+count;if(d->pos>f->size)f->size=d->pos;return (int32_t)count;}
int32_t fs_seek(RVFS *fs,uint32_t n,uint32_t hi,uint32_t lo,uint32_t whence){if(n<3)return (fs->stdio&(1u<<n))?-29:-9;RVFd *d=fd(fs,n);if(!d)return -9;uint32_t base;if(whence==0)base=0;else if(whence==1)base=d->pos;else if(whence==2)base=fs->files[d->file].size;else return -22;
    if(hi==0){if(lo>FS_CAP-base)return -22;d->pos=base+lo;}else if(hi==0xffffffffu&&lo){uint32_t neg=0u-lo;if(neg>base)return -22;d->pos=base-neg;}else return -22;return (int32_t)d->pos;}
int32_t fs_unlink(RVFS *fs,const char *name){if(!fs_name(name))return -22;int i=find(fs,name);if(i<0)return -2;for(unsigned j=0;j<FS_FDS;j++)if(fs->fds[j].used&&fs->fds[j].file==(uint32_t)i)return -16;fs->files[i].name[0]=0;fs->files[i].size=0;return 0;}
