#define _POSIX_C_SOURCE 200809L
#include "rv32.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/file.h>
static RV vm;static RVFS fs;static uint8_t ram[RV_SIZE],image[RV_SIZE];
static int32_t stream(void *ctx,int output,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;ssize_t r=output?write((int)fd,buf,n):read((int)fd,buf,n);return r<0?-errno:(int32_t)r;}
/* Portable volume: magic, then repeated name-length, size (little endian), name and data. */
static int read_volume(const char *path){FILE *f=fopen(path,"rb");if(!f)return errno==ENOENT?0:-1;char magic[8];int ok=fread(magic,1,8,f)==8&&!memcmp(magic,"VLKFS1\0\0",8);unsigned count=0;
    while(ok){int n=fgetc(f);if(n==EOF){ok=!ferror(f);break;}uint8_t b[4];if(n<1||n>=(int)FS_NAME||count>=FS_FILES||fread(b,1,4,f)!=4){ok=0;break;}uint32_t size=(uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);RVFile *r=&fs.files[count];if(size>FS_CAP||fread(r->name,1,(size_t)n,f)!=(size_t)n||strlen(r->name)!=(size_t)n||!fs_name(r->name)||fread(r->data,1,size,f)!=size){ok=0;break;}for(unsigned j=0;j<count;j++)if(!strcmp(fs.files[j].name,r->name))ok=0;r->size=size;count++;}
    fclose(f);return ok?0:-1;}
static int save_volume(const char *path){size_t n=strlen(path);char *tmp=malloc(n+12);if(!tmp)return -1;memcpy(tmp,path,n);memcpy(tmp+n,".tmp.XXXXXX",12);int fd=mkstemp(tmp);if(fd<0){free(tmp);return -1;}FILE *f=fdopen(fd,"wb");if(!f){close(fd);unlink(tmp);free(tmp);return -1;}int ok=fwrite("VLKFS1\0\0",1,8,f)==8;
    for(unsigned i=0;i<FS_FILES&&ok;i++){RVFile *r=&fs.files[i];if(!r->name[0])continue;size_t k=strlen(r->name);uint32_t size=r->size;uint8_t b[5]={(uint8_t)k,(uint8_t)size,(uint8_t)(size>>8),(uint8_t)(size>>16),(uint8_t)(size>>24)};ok=fwrite(b,1,5,f)==5&&fwrite(r->name,1,k,f)==k&&fwrite(r->data,1,size,f)==size;}
    if(fflush(f)||fsync(fd))ok=0;
    if(fclose(f))ok=0;
    if(ok&&rename(tmp,path))ok=0;
    if(!ok)unlink(tmp);
    free(tmp);return ok?0:-1;}
int main(int argc,char **argv){int first=1,lock=-1;const char *volume=NULL;if(argc>1&&!strcmp(argv[1],"--volume")){if(argc<4)return 2;volume=argv[2];first=3;size_t n=strlen(volume);char *path=malloc(n+6);if(!path)return 125;memcpy(path,volume,n);memcpy(path+n,".lock",6);lock=open(path,O_CREAT|O_RDWR,0600);free(path);if(lock<0||flock(lock,LOCK_EX|LOCK_NB)||read_volume(volume)){fprintf(stderr,"vlk elf: volume unavailable or invalid\n");return 125;}}
    if(argc<=first){fprintf(stderr,"usage: vlk elf [--volume FILE] FILE [ARG...]\n");return 2;}FILE *f=fopen(argv[first],"rb");if(!f){perror(argv[first]);return 126;}size_t n=fread(image,1,sizeof(image),f);int bad=ferror(f)||fgetc(f)!=EOF;fclose(f);if(bad||rv_load(&vm,ram,image,n,argc-first,(const char *const *)(argv+first))){fprintf(stderr,"vlk elf: invalid static RV32IM ELF\n");return 125;}fs_reset_fds(&fs);int r=rv_run(&vm,100000000,stream,NULL,&fs);if(r){fprintf(stderr,"vlk elf: trap %d at %08x after %u instructions\n",r,vm.pc,vm.steps);return 125;}if(!vm.status&&volume&&save_volume(volume)){fprintf(stderr,"vlk elf: volume commit failed\n");return 125;}if(lock>=0)close(lock);return (int)vm.status;}
