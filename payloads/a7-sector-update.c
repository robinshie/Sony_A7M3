/* Guarded single-sector update. On any write or verification error, restore
 * the exact previous bytes before returning a report. */
#include <stdint.h>

extern const uint8_t expected_header[], stock_sector[], custom_sector[];
enum { TOTAL = 300 * 1024 * 1024, TARGET = 0x8e4f * 512 };
static const char stage[] = "/tmp/jiritsu/libJit.so";
static const char report[] = "/tmp/jiritsu/a7wr.bin";
static const char device[] = "/dev/nflasha15";

static inline long sys(long nr, long a, long b, long c) {
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2) : "memory", "cc");
    return r0;
}
#define sc(n,a,b,c) sys(n,(long)(a),(long)(b),(long)(c))
static void closefd(long fd) { if (fd >= 0) sc(6, fd, 0, 0); }
static int same(const uint8_t *a, const uint8_t *b, unsigned n) {
    for (unsigned i = 0; i < n; ++i) if (a[i] != b[i]) return 0;
    return 1;
}
static long transfer(long fd, uint8_t *p) {
    if (sc(19, fd, TARGET, 0) != TARGET) return -1;
    return sc(3, fd, p, 512);
}
static int confirm(const uint8_t *expected, uint8_t *got) {
    long fd = sc(5, device, 0, 0);
    int good = fd >= 0 && transfer(fd, got) == 512 && same(expected, got, 512);
    closefd(fd);
    return good;
}

struct status {
    uint32_t magic;
    int32_t capacity, header_ok, old_ok, write_n, sync_rc, readback_ok, restore_n, restore_sync, restored_ok;
    uint8_t last_read[512];
};
static struct status status;
static uint8_t header[2048];

__attribute__((constructor)) static void update(void) {
    uint64_t size = 0;
    long fd, rep;
#ifdef RESTORE
    const uint8_t *const old = custom_sector, *const new = stock_sector;
#else
    const uint8_t *const old = stock_sector, *const new = custom_sector;
#endif
    status.magic = 0x41375752;
    status.write_n = status.sync_rc = status.readback_ok = -1;
    status.restore_n = status.restore_sync = status.restored_ok = -1;
    sc(10, stage, 0, 0);
    /* Write-open only. No data is sent until all checks below pass. */
    fd = sc(5, device, 2 | 0x101000, 0);
    if (fd < 0) goto result;
    if (sc(54, fd, 0x80041272, &size) || !size) {
        long end = sc(19, fd, 0, 2);
        if (end > 0) size = (uint32_t)end;
    }
    if (size != TOTAL) goto result;
    status.capacity = (int32_t)size;
    if (sc(19, fd, 0, 0) != 0 || sc(3, fd, header, sizeof header) != sizeof header ||
            !same(header, expected_header, sizeof header)) goto result;
    status.header_ok = 1;
    if (transfer(fd, status.last_read) != 512 || !same(status.last_read, old, 512)) goto result;
    status.old_ok = 1;
    if (sc(19, fd, TARGET, 0) != TARGET) goto result;
    status.write_n = sc(4, fd, new, 512);
    status.sync_rc = sc(118, fd, 0, 0);
    status.readback_ok = confirm(new, status.last_read);
    if (status.write_n == 512 && !status.sync_rc && status.readback_ok) goto result;
    /* Skip a compensating write if the previous bytes are still intact. */
    if (confirm(old, status.last_read)) {
        status.restored_ok = 1;
    } else if (sc(19, fd, TARGET, 0) == TARGET) {
        status.restore_n = sc(4, fd, old, 512);
        status.restore_sync = sc(118, fd, 0, 0);
        status.restored_ok = confirm(old, status.last_read);
    }
result:
    closefd(fd);
    rep = sc(5, report, 1 | 64 | 128, 0600);
    if (rep >= 0) {
        sc(4, rep, &status, sizeof status);
        sc(118, rep, 0, 0);
        closefd(rep);
    }
}
