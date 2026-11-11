#include "a7-fl-sharpness-native.h"
int a7_fl_sharpness_request(uintptr_t base,int value) {
    if(!base||base>UINT32_MAX-0x1617cd||value<-3||value>3)return -1;
    typedef void *(*New)(unsigned);
    typedef void *(*Init)(void *,int);
    typedef void (*Add)(void *,unsigned,void *);
    typedef void (*Request)(const char *,unsigned,void *);
    /* Allocation sizes and ownership transfer follow the original 0x420d18
     * setter. Its model dispatch checks supplied parameters independently.
     * No backupWrite call: preserve the user's saved Creative Style preset. */
    void *parameter=((New)(base+0x15867c))(20);
    if(!parameter)return -2;
    ((Init)(base+0x1617cd))(parameter,value);
    void *list=((New)(base+0x15867c))(20);
    if(!list) {
        typedef void (*Delete)(void *);
        ((Delete)(base+0x159c64))(parameter);return -2;
    }
    ((Init)(base+0x15d230))(list,0);
    ((Add)(base+0x15c7b8))(list,392,parameter);
    ((Request)(base+0x15aa58))("@M00B",38,list);
    /* The native wrapper has no established success-result ABI. */
    return 1;
}
