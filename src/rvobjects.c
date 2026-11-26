#include "rvobjects.h"
static int range(unsigned p,unsigned n){return p<=RO_VPAGES&&n<=RO_VPAGES-p;}
static void release(ROPool *p,unsigned id){if(!id)return;ROObject *o=&p->objects[id-1];if(--o->refs)return;if(!o->period){p->used[o->dense]=0;p->dense--;}p->live--;}
int ro_map(ROPool *p,ROSpace *s,unsigned first,unsigned n){if(!range(first,n)||n>RO_OBJECTS-p->reserved)return -1;for(unsigned i=first;i<first+n;i++)if(s->mapped[i])return -1;for(unsigned i=first;i<first+n;i++){s->mapped[i]=1;s->id[i]=0;}p->reserved+=n;return 0;}
int ro_unmap(ROPool *p,ROSpace *s,unsigned first,unsigned n){if(!range(first,n))return -1;for(unsigned i=first;i<first+n;i++)if(!s->mapped[i])return -1;for(unsigned i=first;i<first+n;i++){release(p,s->id[i]);s->mapped[i]=0;s->id[i]=0;}p->reserved-=n;return 0;}
int ro_fork(ROPool *p,ROSpace *dst,const ROSpace *src){unsigned n=0;if(dst==src)return -1;for(unsigned i=0;i<RO_VPAGES;i++){if(dst->mapped[i])return -1;n+=!!src->mapped[i];}if(n>RO_OBJECTS-p->reserved)return -1;for(unsigned i=0;i<RO_VPAGES;i++){dst->mapped[i]=src->mapped[i];dst->id[i]=src->id[i];if(dst->id[i])p->objects[dst->id[i]-1].refs++;}p->reserved+=n;return 0;}
void ro_drop(ROPool *p,ROSpace *s){for(unsigned i=0;i<RO_VPAGES;i++)if(s->mapped[i]){release(p,s->id[i]);s->mapped[i]=0;s->id[i]=0;p->reserved--;}}
static int valid(const ROSpace *s,uint32_t a,uint32_t n){if(a>RO_PAGE*RO_VPAGES||n>RO_PAGE*RO_VPAGES-a)return 0;if(n)for(unsigned i=a/RO_PAGE;i<=(a+n-1)/RO_PAGE;i++)if(!s->mapped[i])return 0;return 1;}
static uint8_t byte(const ROPool *p,unsigned id,unsigned at){if(!id)return 0;const ROObject *o=&p->objects[id-1];return o->period?o->pattern[at%o->period]:p->data[o->dense][at];}
int ro_read(const ROPool *p,const ROSpace *s,uint32_t a,uint8_t *out,uint32_t n){if(!valid(s,a,n))return -1;for(unsigned i=0;i<n;i++)out[i]=byte(p,s->id[(a+i)/RO_PAGE],(a+i)%RO_PAGE);return 0;}
/* Capacity invariant: every mapped coordinate reserves one possible dense object.
 * Replacing a shared object consumes a reservation already held by this mapping. */
static void assign(ROPool *p,ROSpace *s,unsigned page,const uint8_t *data){unsigned old=s->id[page],tag=0,i=0;while(i<RO_PAGE&&!data[i])i++;if(i==RO_PAGE){release(p,old);s->id[page]=0;return;}for(tag=1;tag<=RO_PERIOD;tag++){for(i=tag;i<RO_PAGE&&data[i]==data[i-tag];i++){}if(i==RO_PAGE)break;}if(tag>RO_PERIOD)tag=0;
    unsigned id=old;if(old&&p->objects[old-1].refs==1){ROObject *o=&p->objects[old-1];if(!o->period){p->used[o->dense]=0;p->dense--;}}else{if(old){release(p,old);p->copies++;}for(id=1;id<=RO_OBJECTS&&p->objects[id-1].refs;id++){}p->live++;}ROObject *o=&p->objects[id-1];o->refs=1;o->period=(uint8_t)tag;
    if(tag){for(i=0;i<tag;i++)o->pattern[i]=data[i];}else{unsigned j=0;while(p->used[j])j++;p->used[j]=1;o->dense=(uint16_t)j;p->dense++;if(p->dense>p->peak_dense)p->peak_dense=p->dense;for(i=0;i<RO_PAGE;i++)p->data[j][i]=data[i];}s->id[page]=(uint16_t)id;
}
int ro_write(ROPool *p,ROSpace *s,uint32_t a,const uint8_t *in,uint32_t n){if(!valid(s,a,n))return -1;uint8_t scratch[RO_PAGE];while(n){unsigned page=a/RO_PAGE,offset=a%RO_PAGE,take=RO_PAGE-offset;if(take>n)take=n;unsigned id=s->id[page];int changed=0;for(unsigned i=0;i<take;i++)if(in[i]!=byte(p,id,offset+i)){changed=1;break;}if(changed){for(unsigned i=0;i<RO_PAGE;i++)scratch[i]=byte(p,id,i);for(unsigned i=0;i<take;i++)scratch[offset+i]=in[i];assign(p,s,page,scratch);}a+=take;in+=take;n-=take;}return 0;}

/* Frequent stores never scan for structure. A changed non-dense or shared page
 * becomes dense once; unique dense pages are updated directly. */
int ro_store(ROPool *p,ROSpace *s,uint32_t a,const uint8_t *in,uint32_t n){
    if(!valid(s,a,n))return -1;
    while(n){unsigned page=a/RO_PAGE,at=a%RO_PAGE,take=RO_PAGE-at;if(take>n)take=n;
        unsigned id=s->id[page];ROObject *o=id?&p->objects[id-1]:0;unsigned i=0;
        while(i<take&&in[i]==byte(p,id,at+i))i++;
        if(i<take){
            if(!o||o->refs!=1||o->period){
                unsigned slot=0;while(p->used[slot])slot++;
                for(unsigned j=0;j<RO_PAGE;j++)p->data[slot][j]=byte(p,id,j);
                if(!o||o->refs!=1){if(o){release(p,id);p->copies++;}for(id=1;p->objects[id-1].refs;id++){}p->live++;o=&p->objects[id-1];s->id[page]=(uint16_t)id;}
                o->refs=1;o->period=0;o->dense=(uint16_t)slot;p->used[slot]=1;p->dense++;if(p->dense>p->peak_dense)p->peak_dense=p->dense;
            }
            for(unsigned j=0;j<take;j++)p->data[o->dense][at+j]=in[j];
        }a+=take;in+=take;n-=take;
    }return 0;
}
