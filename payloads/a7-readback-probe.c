/* Sony A7 III ARM/Linux factory probe. No firmware or settings writes. */
#include <stdint.h>

/* ARM EABI Linux calls, no dependency on the camera's libc version. */
static inline long sc3(long nr, long a, long b, long c) {
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2) : "memory", "cc");
    return r0;
}

static long ro(const char *path) { return sc3(5, (long)path, 0, 0); }
static long get(long fd, void *dst, long n) { return sc3(3, fd, (long)dst, n); }
static void closefd(long fd) { sc3(6, fd, 0, 0); }
static long removefile(const char *path) { return sc3(10, (long)path, 0, 0); }

static struct {
    uint32_t magic;
    int32_t uid, device, size_rc, head_n, changed_n, mounts_n;
    uint64_t device_bytes;
    unsigned char head[2048], changed[512], mounts[4096];
} result;

static const char stage[] = "/tmp/jiritsu/libJit.so";
static const char output[] = "/tmp/jiritsu/a7rdo.bin";

__attribute__((constructor)) static void read_camera(void) {
    long fd, out;
    result.magic = 0x41523731;
    result.uid = sc3(199, 0, 0, 0); /* getuid32 */
    result.device = fd = ro("/dev/nflasha15");
    if (fd >= 0) {
        result.size_rc = sc3(54, fd, 0x80081272, (long)&result.device_bytes); /* BLKGETSIZE64 */
        result.head_n = get(fd, result.head, sizeof result.head);
        if (sc3(19, fd, 0x8e4f * 512L, 0) == 0x8e4f * 512L)
            result.changed_n = get(fd, result.changed, sizeof result.changed);
        closefd(fd);
    }
    fd = ro("/proc/mounts");
    if (fd >= 0) {
        result.mounts_n = get(fd, result.mounts, sizeof result.mounts);
        closefd(fd);
    }
    /* Remove only the probe that was just loaded. Its ELF mapping stays valid. */
    removefile(stage);
    /* The only write is a new report on the maintenance volume. */
    out = sc3(5, (long)output, 1 | 64 | 128, 0600);
    if (out >= 0) {
        sc3(4, out, (long)&result, sizeof result);
        sc3(118, out, 0, 0);
        closefd(out);
    }
}
