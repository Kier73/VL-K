/* Native boundary checks for the common loader and Multiboot module range checks. */
#include "rv32.h"
#include "module.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>
static RV vm,prior;
static uint8_t ram[RV_SIZE],before[RV_SIZE],image[RV_SIZE];
int main(int argc,char **argv){
    assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);size_t n=fread(image,1,sizeof(image),f);assert(!ferror(f)&&feof(f));fclose(f);
    const char *args[]={"external","kernel"},*env[]={"MODE=vlk"};assert(!rv_load_env(&vm,ram,image,n,2,args,1,env));
    memcpy(&prior,&vm,sizeof(vm));memcpy(before,ram,sizeof(ram));
    /* A failure at the entry validation (after PT_LOAD parsing) leaves live state intact. */
    uint8_t saved[4];memcpy(saved,image+24,4);memset(image+24,0,4);
    assert(rv_load_env(&vm,ram,image,n,2,args,1,env));assert(!memcmp(&vm,&prior,sizeof(vm))&&!memcmp(ram,before,sizeof(ram)));memcpy(image+24,saved,4);
    char bad[4097];memset(bad,'a',sizeof(bad)-1);bad[4096]=0;const char *bad_env[]={bad};
    assert(rv_load_env(&vm,ram,image,n,2,args,1,bad_env));assert(!memcmp(&vm,&prior,sizeof(vm))&&!memcmp(ram,before,sizeof(ram)));
    assert(mb_top(31744)==32*1024*1024&&mb_top(0xffffffffu)==0);
    assert(mb_range(4096,16,32768)&&!mb_range(0,16,32768)&&!mb_range(32760,16,32768));
    assert(mb_module(0x800000,0x801000,0x2000000,0x700000,RV_SIZE));
    assert(!mb_module(0x600000,0x601000,0x2000000,0x700000,RV_SIZE));
    assert(!mb_module(0x800000,0x800000,0x2000000,0x700000,RV_SIZE));
    assert(!mb_module(0x800000,0xd00000,0x2000000,0x700000,RV_SIZE));
    assert(!mb_module(0x1fff000,0x2001000,0x2000000,0x700000,RV_SIZE));
    puts("late loader failure preserves machine and RAM; Multiboot module bounds passed");return 0;
}
