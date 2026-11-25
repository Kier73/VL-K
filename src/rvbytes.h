#ifndef VL_RVBYTES_H
#define VL_RVBYTES_H
#include <stdint.h>
#define FS_FILES 8u
#define FS_CAP (256u*1024u)
#define FS_PAGE 4096u
#define FS_PAGES (FS_CAP/FS_PAGE)
#define FS_POOL (FS_FILES*FS_PAGES)
#define FS_PATTERN 16u
#define FS_DENSE 255u
/* Zero tag = implicit zero, 1..16 = period, 255 = exclusive dense slot. */
typedef struct {uint16_t slot;uint8_t tag,pattern[FS_PATTERN];} RVPage;
typedef struct {uint8_t used[FS_POOL];uint8_t data[FS_POOL][FS_PAGE];} RVPool;
static inline uint8_t page_byte(const RVPool *pool,const RVPage *p,unsigned i){return p->tag==FS_DENSE?pool->data[p->slot][i]:p->tag?p->pattern[i%p->tag]:0;}
static inline void page_clear(RVPool *pool,RVPage *p){if(p->tag==FS_DENSE)pool->used[p->slot]=0;p->tag=0;p->slot=0;}
/* All pages, including the final page's hidden tail, are represented exactly. */
static inline void page_assign(RVPool *pool,RVPage *p,const uint8_t *data){
    unsigned tag=0,i=0;
    while(i<FS_PAGE&&!data[i])i++;
    if(i<FS_PAGE){for(tag=1;tag<=FS_PATTERN;tag++){for(i=tag;i<FS_PAGE&&data[i]==data[i-tag];i++){}if(i==FS_PAGE)break;}if(tag>FS_PATTERN)tag=FS_DENSE;}
    if(tag==FS_DENSE){unsigned j=p->slot;if(p->tag!=FS_DENSE){for(j=0;j<FS_POOL&&pool->used[j];j++){}/* One slot per possible file page: an unbacked page implies a free slot. */pool->used[j]=1;}p->slot=(uint16_t)j;for(i=0;i<FS_PAGE;i++)pool->data[j][i]=data[i];}
    else {page_clear(pool,p);for(i=0;i<tag;i++)p->pattern[i]=data[i];}
    p->tag=(uint8_t)tag;
}
#endif
