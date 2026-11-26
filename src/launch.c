#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int failure(const char *name) {
    int code=errno;
    fprintf(stderr,"vlk: %s: %s\n",name,strerror(code));
    return code==ENOENT?127:126;
}
int main(int argc,char **argv) {
    const char *usage="usage: vlk run COMMAND [ARG ...] | vlk shell [SHELL ARG ...] | vlk guest PROGRAM [OPTIONS] | vlk debug PROGRAM [--restore FILE] | vlk app PROGRAM INPUT AUTHORITY SINK JOB | vlk pack PROGRAM IMAGE | vlk session ROOT [NAME=ELF ...] | vlk elf FILE [ARG ...] | vlk refine TABLE | vlk ground TABLE | vlk PROGRAM [COUNT]";
    if(argc==1 || (argc==2 && (!strcmp(argv[1],"-h") || !strcmp(argv[1],"--help")))) {
        fprintf(argc==1?stderr:stdout,"%s\n",usage);return argc==1?2:0;
    }
    if(!strcmp(argv[1],"run")) {
        int i=2; if(i<argc&&!strcmp(argv[i],"--")) ++i;
        if(i==argc) { fprintf(stderr,"%s\n",usage);return 2; }
        execvp(argv[i],argv+i);return failure(argv[i]);
    }
    if(!strcmp(argv[1],"shell")) {
        argv[1]=(char *)"/bin/sh";execv(argv[1],argv+1);return failure(argv[1]);
    }
    /* Locate the source-tree portable interpreter relative to this Linux launcher. */
    char path[4096]; ssize_t n=readlink("/proc/self/exe",path,sizeof(path)-1);
    if(n<0) return failure("/proc/self/exe");
    if(n==(ssize_t)sizeof(path)-1) { fprintf(stderr,"vlk: launcher path too long\n");return 126; }
    path[n]='\0';char *slash=strrchr(path,'/');
    if(!slash) return 126;
    const char suffix[]="/../bin/vlk";
    if((size_t)(slash-path)+sizeof(suffix)>sizeof(path)) return 126;
    memcpy(slash,suffix,sizeof(suffix));
    argv[0]=path;execv(path,argv);return failure(path);
}
