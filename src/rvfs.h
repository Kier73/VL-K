#ifndef VL_RVFS_H
#define VL_RVFS_H
#include <stdint.h>
#include "rvbytes.h"
#define FS_FDS 19u
#define FS_OPEN 38u
#define FS_NAME 64u
/* A descriptor is a local reference; the open description owns cursor and access. */
typedef struct {char name[FS_NAME];uint32_t size;RVPage pages[FS_PAGES];} RVFile;
typedef struct {uint32_t object,pos,flags,refs;int stream;} RVOpen;
typedef struct {uint8_t slots[FS_FDS];uint8_t cloexec[FS_FDS];} RVFds;
typedef struct {RVFile files[FS_FILES];RVOpen opens[FS_OPEN];RVPool pool;} RVFS;
/* Internal byte observations; callers hold the kernel object boundary. */
int32_t fs_file_read(const RVFS *,const RVFile *,uint32_t,uint8_t *,uint32_t);
int32_t fs_file_write(RVFS *,RVFile *,uint32_t,const uint8_t *,uint32_t);
void fs_file_clear(RVFS *,RVFile *);
void fs_reset_fds(RVFS *,RVFds *);
void fs_drop_fds(RVFS *,RVFds *);
int fs_name(const char *);
int32_t fs_open(RVFS *,RVFds *,const char *,uint32_t);
int32_t fs_close(RVFS *,RVFds *,uint32_t);
int32_t fs_dup(RVFS *,RVFds *,uint32_t,uint32_t,uint32_t,int);
int32_t fs_fcntl(RVFS *,RVFds *,uint32_t,uint32_t,uint32_t);
int32_t fs_access(RVFS *,RVFds *,uint32_t,int,int *);
int32_t fs_read(RVFS *,RVFds *,uint32_t,uint8_t *,uint32_t);
int32_t fs_write(RVFS *,RVFds *,uint32_t,const uint8_t *,uint32_t);
int32_t fs_seek(RVFS *,RVFds *,uint32_t,uint32_t,uint32_t,uint32_t);
int32_t fs_unlink(RVFS *,const char *);
int32_t fs_statx(RVFS *,RVFds *,uint32_t,const char *,uint32_t,uint8_t *);
#endif
