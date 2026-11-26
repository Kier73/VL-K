#include "rvobjects.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static ROPool p;static ROSpace s[8];static uint8_t eager[8][64*RO_PAGE],buf[RO_PAGE],out[RO_PAGE];
static uint32_t seed=9271;static uint32_t rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static void verify(void){unsigned refs[RO_OBJECTS]={0},reserved=0,live=0,dense=0;for(unsigned j=0;j<8;j++)for(unsigned i=0;i<RO_VPAGES;i++)if(s[j].mapped[i]){reserved++;if(s[j].id[i])refs[s[j].id[i]-1]++;}for(unsigned i=0;i<RO_OBJECTS;i++){assert(refs[i]==p.objects[i].refs);live+=!!refs[i];dense+=!!p.used[i];}assert(reserved==p.reserved&&live==p.live&&dense==p.dense&&dense<=live&&live<=reserved);}
int main(void){assert(!ro_map(&p,&s[0],0,64));for(unsigned i=0;i<RO_PAGE;i++)buf[i]=(uint8_t)(i%7+1);for(unsigned i=0;i<64;i++){assert(!ro_write(&p,&s[0],i*RO_PAGE,buf,RO_PAGE));memcpy(eager[0]+i*RO_PAGE,buf,RO_PAGE);}assert(p.live==64&&!p.dense);for(unsigned j=1;j<8;j++){assert(!ro_fork(&p,&s[j],&s[0]));memcpy(eager[j],eager[0],sizeof(eager[j]));}verify();assert(p.reserved==512&&p.live==64&&!p.dense&&!p.copies);assert(ro_map(&p,&s[0],64,1)<0);assert(ro_fork(&p,&s[1],&s[0])<0);printf("8 address spaces: %u mapped pages, %u periodic objects, %u dense pages, zero fork copies\n",p.reserved,p.live,p.dense);
/* Original owner can disappear; descendants retain the same page identities. */
ro_drop(&p,&s[0]);verify();assert(p.reserved==448&&p.live==64);
assert(!ro_fork(&p,&s[0],&s[7]));verify();assert(p.reserved==512&&p.live==64&&!p.copies);
assert(!ro_read(&p,&s[0],0,out,RO_PAGE)&&!memcmp(out,eager[0],RO_PAGE));
for(unsigned i=0;i<8000;i++){unsigned j=rnd()>>29,a=rnd()%(sizeof(eager[0])-64),n=1+rnd()%64;if(rnd()&0x100){for(unsigned k=0;k<n;k++)buf[k]=(uint8_t)(rnd()>>24);assert(!(i&1?ro_store:ro_write)(&p,&s[j],a,buf,n));memcpy(eager[j]+a,buf,n);}else{assert(!ro_read(&p,&s[j],a,out,n)&&!memcmp(out,eager[j]+a,n));}if(i%127==0)verify();}for(unsigned j=0;j<8;j++)for(unsigned i=0;i<64;i++){assert(!ro_read(&p,&s[j],i*RO_PAGE,out,RO_PAGE)&&!memcmp(out,eager[j]+i*RO_PAGE,RO_PAGE));}verify();printf("8000 mixed operations, 512 full-page comparisons; peak dense=%u, shared-object splits=%u\n",p.peak_dense,p.copies);
/* Full capacity is a promise: every reserved page can become private dense. */
for(unsigned j=0;j<8;j++)for(unsigned i=0;i<64;i++){for(unsigned k=0;k<RO_PAGE;k++)buf[k]=(uint8_t)(rnd()>>24);assert(!ro_write(&p,&s[j],i*RO_PAGE,buf,RO_PAGE));}
verify();assert(p.dense==512&&p.live==512);assert(ro_unmap(&p,&s[0],63,2)<0&&p.reserved==512);assert(ro_write(&p,&s[0],64*RO_PAGE-1,buf,2)<0);assert(!ro_unmap(&p,&s[0],0,1)&&!ro_map(&p,&s[0],0,1));assert(!ro_read(&p,&s[0],0,out,RO_PAGE));for(unsigned i=0;i<RO_PAGE;i++)assert(!out[i]);for(unsigned j=0;j<8;j++)ro_drop(&p,&s[j]);verify();assert(!p.reserved&&!p.live&&!p.dense);puts("512 dense reservations fulfilled, invalid ranges atomic, zero remap and all references reclaimed");
assert(!ro_map(&p,&s[0],0,257));assert(ro_fork(&p,&s[1],&s[0])<0&&p.reserved==257&&!s[1].mapped[0]);
assert(!ro_map(&p,&s[1],0,1));memset(buf,5,sizeof(buf));assert(!ro_write(&p,&s[1],0,buf,RO_PAGE));assert(p.live==1&&!p.dense);memset(buf,0,sizeof(buf));assert(!ro_write(&p,&s[1],0,buf,RO_PAGE));assert(!p.live&&!p.dense);ro_drop(&p,&s[0]);ro_drop(&p,&s[1]);verify();puts("owner-independent lifetime, overcommit refusal and periodic-to-zero reclaim passed");return 0;}
