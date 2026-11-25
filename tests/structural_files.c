#include "rvfs.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static RVFS fs;static RVFds fds;static uint8_t model[FS_FILES][FS_CAP],data[FS_CAP],out[FS_CAP];static unsigned sizes[FS_FILES];
static uint32_t rng=891;static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static unsigned used(void){unsigned n=0;for(unsigned i=0;i<FS_POOL;i++)n+=!!fs.pool.used[i];return n;}
static void invariant(void){unsigned refs[FS_POOL]={0};for(unsigned f=0;f<FS_FILES;f++)for(unsigned p=0;p<FS_PAGES;p++){RVPage *q=&fs.files[f].pages[p];assert(q->tag<=FS_PATTERN||q->tag==FS_DENSE);if(q->tag==FS_DENSE){assert(q->slot<FS_POOL);refs[q->slot]++;}}for(unsigned j=0;j<FS_POOL;j++)assert(refs[j]==(unsigned)!!fs.pool.used[j]);}
int main(void){
    fs_reset_fds(&fs,&fds);int fd=fs_open(&fs,&fds,"periodic",0102);assert(fd==3);
    for(unsigned i=0;i<FS_PAGE;i++)data[i]=(uint8_t)(i%7+1);
    assert(fs_write(&fs,&fds,fd,data,FS_PAGE)==FS_PAGE);assert(fs.files[0].pages[0].tag==7&&!used());
    int d=fs_dup(&fs,&fds,fd,0,0,0);assert(d==4&&fs_seek(&fs,&fds,d,0,17,0)==17);uint8_t b=99;
    assert(fs_write(&fs,&fds,fd,&b,1)==1&&used()==1);assert(fs_seek(&fs,&fds,d,0,17,0)==17&&fs_read(&fs,&fds,d,&b,1)==1&&b==99);
    assert(fs_seek(&fs,&fds,fd,0,17,0)==17&&fs_write(&fs,&fds,d,data+17,1)==1&&!used()&&fs.files[0].pages[0].tag==7);
    fs_drop_fds(&fs,&fds);assert(!fs_unlink(&fs,"periodic"));
    for(unsigned k=0;k<5000;k++){unsigned f=next()%FS_FILES,op=next()%12;RVFile *r=&fs.files[f];
        if(op==0){fs_file_clear(&fs,r);memset(model[f],0,FS_CAP);sizes[f]=0;}
        else if(op<7){unsigned pos=next()%FS_CAP,n=next()%8193;if(n>FS_CAP-pos)n=FS_CAP-pos;unsigned period=next()%20;
            for(unsigned i=0;i<n;i++)data[i]=period==0?0:period<=16?(uint8_t)(i%period+1):(uint8_t)next();
            assert(fs_file_write(&fs,r,pos,data,n)==(int32_t)n);if(n){memcpy(model[f]+pos,data,n);if(pos+n>sizes[f])sizes[f]=pos+n;}}
        else{unsigned pos=next()%FS_CAP,n=next()%8193,expect=pos>=sizes[f]?0:sizes[f]-pos;if(expect>n)expect=n;assert(fs_file_read(&fs,r,pos,out,n)==(int32_t)expect&&!memcmp(out,model[f]+pos,expect));}
        assert(r->size==sizes[f]);if(k%100==0){invariant();for(unsigned j=0;j<FS_FILES;j++){assert(fs_file_read(&fs,&fs.files[j],0,out,FS_CAP)==(int32_t)sizes[j]);assert(!memcmp(out,model[j],sizes[j]));}}}
    for(unsigned f=0;f<FS_FILES;f++){for(unsigned i=0;i<FS_CAP;i++)data[i]=(uint8_t)next();assert(fs_file_write(&fs,&fs.files[f],0,data,FS_CAP)==FS_CAP);memcpy(model[f],data,FS_CAP);}
    invariant();assert(used()==FS_POOL);for(unsigned f=0;f<FS_FILES;f++){assert(fs_file_read(&fs,&fs.files[f],0,out,FS_CAP)==FS_CAP&&!memcmp(out,model[f],FS_CAP));}
    assert(fs_file_write(&fs,&fs.files[0],FS_CAP-1,data,2)==-28&&used()==FS_POOL);memset(data,0,FS_CAP);assert(fs_file_write(&fs,&fs.files[0],0,data,FS_CAP)==FS_CAP&&used()==FS_POOL-FS_PAGES);
    for(unsigned f=0;f<FS_FILES;f++)fs_file_clear(&fs,&fs.files[f]);
    invariant();assert(!used());puts("5000 eager-oracle operations; shared descriptor mutation and repair; 512 dense slots filled, reclaimed and verified");return 0;
}
