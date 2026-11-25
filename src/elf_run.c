#define _POSIX_C_SOURCE 200809L
#include "rv32.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/file.h>
static RV vm;static RVFS fs;static RVFds fds;static uint8_t ram[RV_SIZE],image[RV_SIZE];
static int32_t stream(void *ctx,int output,uint32_t fd,uint8_t *buf,uint32_t n){(void)ctx;ssize_t r=output?write((int)fd,buf,n):read((int)fd,buf,n);return r<0?-errno:(int32_t)r;}
/* V1 dense file bytes; V2 page tags with exact zero/periodic/dense realizations. */
static int read_volume(const char *path){FILE *f=fopen(path,"rb");if(!f)return errno==ENOENT?0:-1;char magic[8];int ok=fread(magic,1,8,f)==8;int compact=ok&&!memcmp(magic,"VLKFS2\0\0",8);ok=ok&&(compact||!memcmp(magic,"VLKFS1\0\0",8));unsigned count=0;
    while(ok){int n=fgetc(f);if(n==EOF){ok=!ferror(f);break;}uint8_t b[4];if(n<1||n>=(int)FS_NAME||count>=FS_FILES||fread(b,1,4,f)!=4){ok=0;break;}uint32_t size=(uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);RVFile *r=&fs.files[count];if(size>FS_CAP||fread(r->name,1,(size_t)n,f)!=(size_t)n||strlen(r->name)!=(size_t)n||!fs_name(r->name)){ok=0;break;}for(unsigned j=0;j<count;j++)if(!strcmp(fs.files[j].name,r->name))ok=0;
        for(uint32_t pos=0;ok&&pos<size;pos+=FS_PAGE){uint8_t page[FS_PAGE],pattern[FS_PATTERN];uint32_t k=size-pos;if(k>FS_PAGE)k=FS_PAGE;int tag=compact?fgetc(f):(int)FS_DENSE;
            if(tag==FS_DENSE)ok=fread(page,1,k,f)==k;
            else if(tag>=0&&tag<=(int)FS_PATTERN){ok=fread(pattern,1,(size_t)tag,f)==(size_t)tag;for(uint32_t i=0;ok&&i<k;i++)page[i]=tag?pattern[i%(unsigned)tag]:0;}
            else ok=0;
            if(ok)ok=fs_file_write(&fs,r,pos,page,k)==(int32_t)k;}
        count++;}
    fclose(f);return ok?0:-1;}
static int save_volume(const char *path,int compact){size_t n=strlen(path);char *tmp=malloc(n+12);if(!tmp)return -1;memcpy(tmp,path,n);memcpy(tmp+n,".tmp.XXXXXX",12);int fd=mkstemp(tmp);if(fd<0){free(tmp);return -1;}FILE *f=fdopen(fd,"wb");if(!f){close(fd);unlink(tmp);free(tmp);return -1;}int ok=fwrite(compact?"VLKFS2\0\0":"VLKFS1\0\0",1,8,f)==8;
    for(unsigned i=0;i<FS_FILES&&ok;i++){RVFile *r=&fs.files[i];if(!r->name[0])continue;size_t k=strlen(r->name);uint32_t size=r->size;uint8_t b[5]={(uint8_t)k,(uint8_t)size,(uint8_t)(size>>8),(uint8_t)(size>>16),(uint8_t)(size>>24)};ok=fwrite(b,1,5,f)==5&&fwrite(r->name,1,k,f)==k;
        for(uint32_t pos=0;ok&&pos<size;pos+=FS_PAGE){uint32_t len=size-pos;if(len>FS_PAGE)len=FS_PAGE;const RVPage *p=&r->pages[pos/FS_PAGE];uint8_t page[FS_PAGE];
            if(compact){ok=fputc(p->tag,f)!=EOF;if(ok&&p->tag!=FS_DENSE){ok=fwrite(p->pattern,1,p->tag,f)==p->tag;continue;}}
            if(ok){ok=fs_file_read(&fs,r,pos,page,len)==(int32_t)len&&fwrite(page,1,len,f)==len;}}}
    if(fflush(f)||fsync(fd))ok=0;
    if(fclose(f))ok=0;
    if(ok&&rename(tmp,path))ok=0;
    if(!ok)unlink(tmp);
    free(tmp);return ok?0:-1;}
int main(int argc,char **argv){int first=1,lock=-1,envc=0,compact=0;const char *envp[64],*volume=NULL;if(argc>1&&(!strcmp(argv[1],"--volume")||!strcmp(argv[1],"--compact-volume"))){compact=!strcmp(argv[1],"--compact-volume");if(argc<4)return 2;volume=argv[2];first=3;size_t n=strlen(volume);char *path=malloc(n+6);if(!path)return 125;memcpy(path,volume,n);memcpy(path+n,".lock",6);lock=open(path,O_CREAT|O_RDWR,0600);free(path);if(lock<0||flock(lock,LOCK_EX|LOCK_NB)||read_volume(volume)){fprintf(stderr,"vlk elf: volume unavailable or invalid\n");return 125;}}
    while(first<argc&&!strcmp(argv[first],"--env")){if(first+1>=argc||envc==64||!strchr(argv[first+1],'=')||argv[first+1][0]=='=')return 2;envp[envc++]=argv[first+1];first+=2;}
    if(argc<=first){fprintf(stderr,"usage: vlk elf [--volume FILE | --compact-volume FILE] [--env KEY=VALUE] FILE [ARG...]\n");return 2;}FILE *f=fopen(argv[first],"rb");if(!f){perror(argv[first]);return 126;}size_t n=fread(image,1,sizeof(image),f);int bad=ferror(f)||fgetc(f)!=EOF;fclose(f);if(bad||rv_load_env(&vm,ram,image,n,argc-first,(const char *const *)(argv+first),envc,envp)){fprintf(stderr,"vlk elf: invalid static RV32IM ELF\n");return 125;}fs_reset_fds(&fs,&fds);int r=rv_run(&vm,100000000,stream,NULL,&fs,&fds);if(r){fprintf(stderr,"vlk elf: trap %d at %08x after %u instructions\n",r,vm.pc,vm.steps);return 125;}if(!vm.status&&volume&&save_volume(volume,compact)){fprintf(stderr,"vlk elf: volume commit failed\n");return 125;}if(lock>=0)close(lock);return (int)vm.status;}
