#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "iog_map_preferences.h"
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

enum { RecordBytes=24 };
static unsigned nonce;
static bool Valid(const IogMapPreferences *p)
{
    if(!p)return false;
    unsigned used=0;
    for(unsigned n=0;n<5;n++){
        if(p->bindings[n]>=6||(used&(1u<<p->bindings[n])))return false;
        used|=1u<<p->bindings[n];
    }
    return true;
}
static uint32_t Crc(const uint8_t *p,size_t size)
{
    uint32_t crc=~0u;
    for(size_t n=0;n<size;n++){
        crc^=p[n];
        for(unsigned bit=0;bit<8;bit++)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1)));
    }
    return ~crc;
}
#ifdef _WIN32
static bool Directory(const wchar_t *path)
{
    DWORD attr=GetFileAttributesW(path);
    return attr!=INVALID_FILE_ATTRIBUTES&&(attr&FILE_ATTRIBUTE_DIRECTORY)&&
        !(attr&FILE_ATTRIBUTE_REPARSE_POINT);
}
static bool Safe(void){return Directory(L"saves")&&Directory(L"saves/maps");}
static bool Read(uint8_t record[RecordBytes])
{
    if(!Safe())return false;
    HANDLE file=CreateFileW(L"saves/maps/controls.iogprefs",GENERIC_READ,
        FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    if(file==INVALID_HANDLE_VALUE)return false;
    BY_HANDLE_FILE_INFORMATION info;uint8_t bytes[RecordBytes+1];DWORD got=0;
    bool ok=GetFileInformationByHandle(file,&info)&&
        !(info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))&&
        ReadFile(file,bytes,sizeof(bytes),&got,NULL)&&got==RecordBytes;
    CloseHandle(file);if(ok)memcpy(record,bytes,RecordBytes);return ok;
}
static bool Write(const uint8_t record[RecordBytes])
{
    if(!Safe())return false;
    DWORD attr=GetFileAttributesW(L"saves/maps/controls.iogprefs");
    if(attr!=INVALID_FILE_ATTRIBUTES&&(attr&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))return false;
    wchar_t temporary[160];HANDLE file=INVALID_HANDLE_VALUE;
    for(unsigned n=0;n<8&&file==INVALID_HANDLE_VALUE;n++){
        swprintf(temporary,sizeof(temporary)/sizeof(*temporary),
            L"saves/maps/controls.iogprefs.tmp-%lu-%u",(unsigned long)GetCurrentProcessId(),++nonce);
        file=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    }
    if(file==INVALID_HANDLE_VALUE)return false;
    DWORD written=0;bool ok=WriteFile(file,record,RecordBytes,&written,NULL)&&
        written==RecordBytes&&FlushFileBuffers(file);CloseHandle(file);
    attr=GetFileAttributesW(L"saves/maps/controls.iogprefs");
    ok=ok&&Safe()&&(attr==INVALID_FILE_ATTRIBUTES||!(attr&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))&&
        MoveFileExW(temporary,L"saves/maps/controls.iogprefs",MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
    if(!ok)DeleteFileW(temporary);return ok;
}
#else
static bool Directory(const char *path)
{struct stat st;return !lstat(path,&st)&&S_ISDIR(st.st_mode)&&!S_ISLNK(st.st_mode);}
static bool Safe(void){return Directory("saves")&&Directory("saves/maps");}
static bool Read(uint8_t record[RecordBytes])
{
    if(!Safe())return false;
    int fd=open("saves/maps/controls.iogprefs",O_RDONLY|O_NOFOLLOW);
    if(fd<0)return false;
    struct stat st;uint8_t bytes[RecordBytes+1];ssize_t size=read(fd,bytes,sizeof(bytes));
    bool ok=!fstat(fd,&st)&&S_ISREG(st.st_mode)&&size==RecordBytes;
    close(fd);if(ok)memcpy(record,bytes,RecordBytes);return ok;
}
static bool Write(const uint8_t record[RecordBytes])
{
    if(!Safe())return false;
    struct stat st;int exists=lstat("saves/maps/controls.iogprefs",&st);
    if(!exists&&!S_ISREG(st.st_mode))return false;
    char temporary[160];int fd=-1;
    for(unsigned n=0;n<8&&fd<0;n++){
        snprintf(temporary,sizeof(temporary),"saves/maps/controls.iogprefs.tmp-%lu-%u",(unsigned long)getpid(),++nonce);
        fd=open(temporary,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    }
    if(fd<0)return false;
    bool ok=write(fd,record,RecordBytes)==RecordBytes&&!fsync(fd);close(fd);
    exists=lstat("saves/maps/controls.iogprefs",&st);
    ok=ok&&Safe()&&(exists||S_ISREG(st.st_mode))&&
        !rename(temporary,"saves/maps/controls.iogprefs");
    if(!ok)unlink(temporary);return ok;
}
#endif
bool IogMapPreferencesLoad(IogMapPreferences *preferences)
{
    if(!preferences)return false;
    uint8_t bytes[RecordBytes];
    if(!Read(bytes)||memcmp(bytes,"IOGMAPC1",8))return false;
    for(unsigned n=14;n<20;n++)if(bytes[n])return false;
    uint32_t expected=0;for(unsigned n=0;n<4;n++)expected|=(uint32_t)bytes[20+n]<<(8*n);
    if(Crc(bytes,20)!=expected||bytes[8]>1)return false;
    IogMapPreferences value;value.radar=bytes[8]!=0;memcpy(value.bindings,bytes+9,5);
    if(!Valid(&value))return false;*preferences=value;return true;
}
bool IogMapPreferencesSave(const IogMapPreferences *preferences)
{
    if(!Valid(preferences))return false;
    uint8_t bytes[RecordBytes]={0};memcpy(bytes,"IOGMAPC1",8);
    bytes[8]=preferences->radar;memcpy(bytes+9,preferences->bindings,5);
    uint32_t crc=Crc(bytes,20);for(unsigned n=0;n<4;n++)bytes[20+n]=(uint8_t)(crc>>(8*n));
    return Write(bytes);
}
