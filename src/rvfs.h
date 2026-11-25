#ifndef VL_RVFS_H
#define VL_RVFS_H
#include <stdint.h>
#define FS_FILES 8u
#define FS_FDS 16u
#define FS_CAP (256u*1024u)
#define FS_NAME 64u
typedef struct {char name[FS_NAME];uint32_t size;uint8_t data[FS_CAP];} RVFile;
typedef struct {uint32_t file,pos,flags;int used;} RVFd;
typedef struct {RVFile files[FS_FILES];RVFd fds[FS_FDS];unsigned stdio;} RVFS;
void fs_reset_fds(RVFS *);
int fs_name(const char *);
int32_t fs_open(RVFS *,const char *,uint32_t);
int32_t fs_close(RVFS *,uint32_t);
int32_t fs_read(RVFS *,uint32_t,uint8_t *,uint32_t);
int32_t fs_write(RVFS *,uint32_t,const uint8_t *,uint32_t);
int32_t fs_seek(RVFS *,uint32_t,uint32_t,uint32_t,uint32_t);
int32_t fs_unlink(RVFS *,const char *);
#endif
