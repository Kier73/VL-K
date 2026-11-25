#include "rv32.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
static RV vm;static uint8_t ram[RV_SIZE],image[RV_SIZE];
static int32_t stream(void *ctx,int output,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;ssize_t r=output?write((int)fd,buf,n):read((int)fd,buf,n);return r<0?-errno:(int32_t)r;}
int main(int argc,char **argv){if(argc<2){fprintf(stderr,"usage: vlk elf FILE [ARG...]\n");return 2;}FILE *f=fopen(argv[1],"rb");if(!f){perror(argv[1]);return 126;}size_t n=fread(image,1,sizeof(image),f);int bad=ferror(f)||fgetc(f)!=EOF;fclose(f);if(bad||rv_load(&vm,ram,image,n,argc-1,(const char *const *)(argv+1))){fprintf(stderr,"vlk elf: invalid static RV32IM ELF\n");return 125;}int r=rv_run(&vm,100000000,stream,NULL);if(r){fprintf(stderr,"vlk elf: trap %d at %08x after %u instructions\n",r,vm.pc,vm.steps);return 125;}return (int)vm.status;}
