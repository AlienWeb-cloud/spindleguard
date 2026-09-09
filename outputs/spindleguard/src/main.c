/* SPDX-License-Identifier: GPL-2.0-or-later */
#define FUSE_USE_VERSION 26
#include <fuse.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <time.h>
#include <unistd.h>
#include "loopback_subset.h"

static int rootfd;
static dev_t rootdev;
static const char *write_prefix;
static unsigned slow_ms;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready = PTHREAD_COND_INITIALIZER;
static unsigned long next_ticket, serving;
static _Thread_local uint64_t file_tag;
static uint64_t tag(const char *path) {
    uint64_t h=14695981039346656037ULL;
    for(const unsigned char *p=(const unsigned char *)(path?path:"");*p;++p) { h^=*p; h*=1099511628211ULL; }
    return h;
}
static double now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}
/* Paths are deliberately omitted from structured logs to avoid log injection
 * and disclosure. FUSE-T may not provide the original caller's PID. */
static void event(const char *state, const char *op, unsigned long ticket, double start) {
    fprintf(stderr, "{\"event\":\"%s\",\"op\":\"%s\",\"ticket\":%lu,\"time\":%.6f,\"wait_ms\":%.3f,\"pending\":%lu,\"file_tag\":\"%016llx\"}\n",
        state,op,ticket,now(),(now()-start)*1000,next_ticket-serving-1,(unsigned long long)file_tag);
}
static unsigned long enter(const char *op,const char *path) {
    file_tag=tag(path);
    pthread_mutex_lock(&mutex);
    unsigned long t=next_ticket++;
    double start=now();
    event("queued",op,t,start);
    while(t!=serving) pthread_cond_wait(&ready,&mutex);
    event("start",op,t,start);
    pthread_mutex_unlock(&mutex);
    return t;
}
static void leave(const char *op,unsigned long t) {
    pthread_mutex_lock(&mutex);
    event("finish",op,t,now());
    ++serving;
    pthread_cond_broadcast(&ready);
    pthread_mutex_unlock(&mutex);
}
static int writable(const char *path) {
    if(!write_prefix || !path) return 0;
    size_t n=strlen(write_prefix);
    return !strncmp(path,write_prefix,n) && (path[n]=='/' || path[n]==0);
}
/* Descriptor-relative walk: never follow symlinks, '..', or a nested volume.
 * All backing filesystem calls, including this walk, occur inside the queue.
 * External rename/hardlink races are outside this disposable-data prototype. */
static int beneath(const char *path,int flags,mode_t mode) {
    if(!path || path[0]!='/') return -EINVAL;
    if(strlen(path)>=PATH_MAX) return -ENAMETOOLONG;
    char copy[PATH_MAX]; strcpy(copy,path+1);
    int fd=dup(rootfd);
    if(fd<0) return -errno;
    char *save=NULL,*part=strtok_r(copy,"/",&save);
    while(part) {
        if(!strcmp(part,".") || !strcmp(part,"..")) { close(fd); return -EPERM; }
        char *next=strtok_r(NULL,"/",&save);
        int nf=openat(fd,part,(next ? O_RDONLY|O_DIRECTORY : flags)|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK,mode);
        int e=errno; close(fd);
        if(nf<0) return -e;
        fd=nf;
        struct stat st;
        if(fstat(fd,&st)<0) { e=errno; close(fd); return -e; }
        if(st.st_dev!=rootdev) { close(fd); return -EXDEV; }
        if(!S_ISDIR(st.st_mode) && !S_ISREG(st.st_mode)) { close(fd); return -EPERM; }
        part=next;
    }
    return fd;
}
#define BEGIN(op) unsigned long ticket=enter(op,p)
#define END(op,res) do { int result=(res); leave(op,ticket); return result; } while(0)
static int sg_getattr(const char *p,struct stat *st) {
    BEGIN("metadata"); int fd=beneath(p,O_RDONLY,0),r;
    if(fd<0) r=fd;
    else { r=fstat(fd,st)<0 ? -errno:0; close(fd); }
    if(!r && !writable(p)) st->st_mode &= ~0222;
    END("metadata",r);
}
static int sg_fgetattr(const char *p,struct stat *st,struct fuse_file_info *fi) {
    BEGIN("metadata"); int r=loopback_fgetattr(p,st,fi);
    if(!r && !writable(p)) st->st_mode &= ~0222;
    END("metadata",r);
}
static int do_open(const char *p,mode_t mode,struct fuse_file_info *fi,int create) {
    int writing=(fi->flags&O_ACCMODE)!=O_RDONLY || (fi->flags&O_TRUNC) || create;
    if(writing && !writable(p)) return -EROFS;
    /* Delay truncation until type and hardlink checks have passed. */
    int flags=fi->flags & ~O_TRUNC;
    if(create) flags|=O_CREAT|O_EXCL;
    int fd=beneath(p,flags,mode & 0777);
    if(fd<0) return fd;
    struct stat st;
    if(fstat(fd,&st)<0) { int e=errno; close(fd); return -e; }
    if(!S_ISREG(st.st_mode) || (writing && st.st_nlink!=1)) { close(fd); return -EPERM; }
    if((fi->flags&O_TRUNC) && ftruncate(fd,0)<0) { int e=errno; close(fd); return -e; }
    fi->fh=fd; fi->direct_io=1; fi->keep_cache=0;
    return 0;
}
static int sg_open(const char *p,struct fuse_file_info *fi) {
    BEGIN("open"); END("open",do_open(p,0,fi,0));
}
static int sg_create(const char *p,mode_t mode,struct fuse_file_info *fi) {
    BEGIN("create"); END("create",do_open(p,mode,fi,1));
}
static int sg_opendir(const char *p,struct fuse_file_info *fi) {
    BEGIN("directory"); int fd=beneath(p,O_RDONLY|O_DIRECTORY,0);
    if(fd<0) END("directory",fd);
    struct loopback_dirp *d=calloc(1,sizeof(*d));
    if(!d) { close(fd); END("directory",-ENOMEM); }
    d->dp=fdopendir(fd);
    if(!d->dp) { int e=errno; close(fd); free(d); END("directory",-e); }
    fi->fh=(uintptr_t)d; END("directory",0);
}
static int sg_readdir(const char *p,void *b,fuse_fill_dir_t f,off_t off,struct fuse_file_info *fi) {
    BEGIN("directory"); END("directory",loopback_readdir(p,b,f,off,fi));
}
static int sg_releasedir(const char *p,struct fuse_file_info *fi) {
    BEGIN("close_directory"); END("close_directory",loopback_releasedir(p,fi));
}
static int sg_read(const char *p,char *b,size_t n,off_t off,struct fuse_file_info *fi) {
    BEGIN("read");
    if(slow_ms) { struct timespec t={slow_ms/1000,(slow_ms%1000)*1000000L}; while(nanosleep(&t,&t)<0 && errno==EINTR) {} }
    END("read",loopback_read(p,b,n,off,fi));
}
static int sg_write(const char *p,const char *b,size_t n,off_t off,struct fuse_file_info *fi) {
    BEGIN("write");
    if(!writable(p) || (fi->flags&O_ACCMODE)==O_RDONLY) END("write",-EROFS);
    struct stat st;
    if(fstat(fi->fh,&st)<0) END("write",-errno);
    if(st.st_nlink!=1) END("write",-EPERM);
    END("write",loopback_write(p,b,n,off,fi));
}
static int sg_flush(const char *p,struct fuse_file_info *fi) {
    BEGIN("flush"); END("flush",loopback_flush(p,fi));
}
static int sg_release(const char *p,struct fuse_file_info *fi) {
    BEGIN("close"); END("close",loopback_release(p,fi));
}
static int sg_fsync(const char *p,int d,struct fuse_file_info *fi) {
    BEGIN("sync"); END("sync",loopback_fsync(p,d,fi));
}
static int sg_statfs(const char *p,struct statvfs *st) {
    (void)p; BEGIN("metadata"); END("metadata",fstatvfs(rootfd,st)<0 ? -errno:0);
}
static int sg_truncate(const char *p,off_t n) {
    BEGIN("truncate");
    if(!writable(p)) END("truncate",-EROFS);
    int fd=beneath(p,O_WRONLY,0),r=0;
    if(fd<0) END("truncate",fd);
    struct stat st;
    if(fstat(fd,&st)<0) r=-errno;
    else if(!S_ISREG(st.st_mode)||st.st_nlink!=1) r=-EPERM;
    else if(ftruncate(fd,n)<0) r=-errno;
    close(fd); END("truncate",r);
}
static struct fuse_operations ops={
    .getattr=sg_getattr,.fgetattr=sg_fgetattr,.open=sg_open,.create=sg_create,
    .read=sg_read,.write=sg_write,.opendir=sg_opendir,.readdir=sg_readdir,
    .releasedir=sg_releasedir,.release=sg_release,.flush=sg_flush,
    .fsync=sg_fsync,.statfs=sg_statfs,.truncate=sg_truncate
};
int main(int argc,char **argv) {
    if(argc<3 || argc>5) {
        fprintf(stderr,"usage: %s TEST_SOURCE MOUNTPOINT [WRITE_PREFIX|-] [TEST_READ_DELAY_MS]\n",argv[0]); return 2;
    }
    char source[PATH_MAX],mountpoint[PATH_MAX];
    if(!realpath(argv[1],source)||!realpath(argv[2],mountpoint)) { perror("realpath"); return 2; }
    if(!strncmp(source,"/Volumes/",9)||!strncmp(mountpoint,"/Volumes/",9)) {
        fprintf(stderr,"Prototype refuses /Volumes paths. Use disposable directories.\n"); return 2;
    }
    size_t n=strlen(source),m=strlen(mountpoint);
    if((!strncmp(source,mountpoint,m)&&(source[m]=='/'||source[m]==0)) ||
       (!strncmp(mountpoint,source,n)&&(mountpoint[n]=='/'||mountpoint[n]==0))) {
        fprintf(stderr,"Source and mount must be disjoint.\n"); return 2;
    }
    rootfd=open(source,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(rootfd<0) { perror("source"); return 2; }
    struct stat st;
    if(fstat(rootfd,&st)<0) return 2;
    rootdev=st.st_dev;
    int marker=openat(rootfd,".spindleguard-test-root",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(marker<0) { fprintf(stderr,"Missing disposable test root marker.\n"); return 2; }
    close(marker);
    /* Prevent two instances using the same test source. This is not a
       machine-wide physical-disk broker; multi-root mounts are deferred. */
    if(flock(rootfd,LOCK_EX|LOCK_NB)<0) { perror("source already in use"); return 2; }
    if(argc>=4 && strcmp(argv[3],"-")) {
        write_prefix=argv[3];
        if(write_prefix[0]!='/' || strlen(write_prefix)<2 || strstr(write_prefix,"..") ||
           write_prefix[strlen(write_prefix)-1]=='/') return 2;
        int fd=beneath(write_prefix,O_RDONLY|O_DIRECTORY,0);
        if(fd<0) { fprintf(stderr,"Write prefix must be an existing safe test directory.\n"); return 2; }
        close(fd);
    }
    if(argc==5) { char *end; long delay=strtol(argv[4],&end,10); if(*end||delay<0||delay>5000) return 2; slow_ms=(unsigned)delay; }
    setvbuf(stderr,NULL,_IOLBF,0);
    fprintf(stderr,"SpindleGuard test-only: one root, FIFO concurrency=1, caller PID unavailable on NFS backend\n");
    char *args[]={argv[0],"-f","-o","backend=nfs,noattrcache,nobrowse,nonamedattr",mountpoint,NULL};
    int result=fuse_main(5,args,&ops,NULL);
    close(rootfd); return result;
}
