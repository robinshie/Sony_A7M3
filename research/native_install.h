#ifndef NATIVE_INSTALL_H
#define NATIVE_INSTALL_H
#include <stdint.h>
/* Standard ARM Linux syscall numbers/ABI. The shim is fault-injected offline. */
typedef long (*NativeInstallSyscall)(void *,long,long,long,long,long,long,long);
typedef struct {
    const unsigned char *bytes;
    uint32_t size;
    unsigned char sha256[32];
} NativeInstallFile;
typedef struct {
    uint32_t version,placeholder;
    /* SHA-256 of a separately reviewed real-module integration proof. */
    unsigned char module_attestation[32];
    NativeInstallFile files[3]; /* a7fl.so, Simplified Chinese, English */
    uint32_t old_locale_sizes[2],view_size;
    unsigned char old_locale_sha[2][32],view_sha[32];
} NativeInstallBundle;
typedef struct {
    uint32_t magic,version,phase,created,published,backed_up;
    int32_t status,first_error,rollback_ok,readonly_confirmed;
    unsigned char bundle_sha[32];
} NativeInstallReport;
/* Caller must compile/pin expected_bundle_sha and supply a non-placeholder
 * attested bundle. Returns0success; negativesfail. Success means files staged,
 * published and /usr read-only. This NEVER changes view or activates the loader.
 * Journal /setting/A7FL.INSTALL is retained on success/failure. Existing journal
 * stops a new attempt; there is deliberately no automatic crash resume.
 */
int native_install_run(const NativeInstallBundle *,const unsigned char expected_bundle_sha[32],
                       NativeInstallSyscall,void *,NativeInstallReport *);
void native_install_bundle_sha(const NativeInstallBundle *,unsigned char [32]);
long native_install_linux_syscall(void *,long,long,long,long,long,long,long);
#endif
