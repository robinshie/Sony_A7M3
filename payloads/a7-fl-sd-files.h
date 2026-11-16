#ifndef A7_FL_SD_FILES_H
#define A7_FL_SD_FILES_H
#include <stdint.h>
#define A7_SD_FILES 32
#define A7_SD_BYTES 16384
struct a7_sd_api {
 int (*first)(const char*,unsigned,void*);
 int (*next)(void*);
 void *(*open)(const char*,const char*);
 unsigned (*read)(void*,unsigned,unsigned,void*);
 int (*close)(void*);
 int (*eof)(void*);
 int (*error)(void*);
 const unsigned char *(*drive_info)(void*);
 uint32_t (*mounted)(void);
};
struct a7_sd_list {
 unsigned count;
 char paths[A7_SD_FILES][260];
 char internal[A7_SD_FILES];
};
/* Caller owns UI serialization, verified library bindings and device context. */
int a7_sd_list_files(const struct a7_sd_api*,char,struct a7_sd_list*);
int a7_sd_read_file(const struct a7_sd_api*,const char*,char,unsigned char*,unsigned*);
#endif
