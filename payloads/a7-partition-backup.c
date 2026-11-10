/* Bounded raw reads from the A7 III's usr partition. Scratch data uses tmpfs. */
#include <stdint.h>

enum { CHUNK = 4 * 1024 * 1024, TOTAL = 300 * 1024 * 1024 };
static const char stage[] = "/tmp/jiritsu/libJit.so";
static const char scratch[] = "/tmp/jiritsu/a7ram";
static const char request[] = "/tmp/jiritsu/a7ram/req.bin";
static const char reply[] = "/tmp/jiritsu/a7ram/data.bin";
static const char owner[] = "/tmp/jiritsu/a7ram/tag.bin";
static const uint32_t tag = 0x41375342;
static uint8_t buf[65536];
static uint32_t crc_table[256];

static inline long sys(long nr, long a, long b, long c, long d, long e) {
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2), "r"(r3), "r"(r4) : "memory", "cc");
    return r0;
}
#define s3(n,a,b,c) sys(n,(long)(a),(long)(b),(long)(c),0,0)
static void closefd(long fd) { if (fd >= 0) s3(6, fd, 0, 0); }
static long readall(long fd, void *p, long n) {
    long i = 0;
    while (i < n) {
        long r = s3(3, fd, (uint8_t *)p + i, n - i);
        if (r < 0) return r;
        if (!r) break;
        i += r;
    }
    return i;
}
static int writeall(long fd, const void *p, long n) {
    long i = 0;
    while (i < n) {
        long r = s3(4, fd, (const uint8_t *)p + i, n - i);
        if (r <= 0) return 0;
        i += r;
    }
    return 1;
}

static void process(uint32_t index) {
    /* A normal response is 12 bytes of metadata followed by the chunk. */
    uint32_t hdr[3] = { tag, index, 0 };
    uint64_t capacity = 0;
    long dev = -1, out = -1;
    uint32_t crc = ~0u;
    for (unsigned i = 0; i < 256; ++i) {
        uint32_t t = i;
        for (unsigned j = 0; j < 8; ++j) t = (t >> 1) ^ (0xedb88320u & (0u - (t & 1u)));
        crc_table[i] = t;
    }
    if (index >= TOTAL / CHUNK) return;
    dev = s3(5, "/dev/nflasha15", 0, 0);
    if (dev < 0) return;
    if (s3(54, dev, 0x80041272, &capacity) || !capacity) {
        long end = s3(19, dev, 0, 2);
        if (end > 0) capacity = (uint32_t)end;
    }
    if (capacity != TOTAL || s3(19, dev, index * CHUNK, 0) != (long)(index * CHUNK)) goto done;
    s3(10, reply, 0, 0);
    out = s3(5, reply, 1 | 64 | 128, 0600);
    if (out < 0 || !writeall(out, hdr, sizeof hdr)) goto done;
    for (unsigned left = CHUNK; left; left -= sizeof buf) {
        if (readall(dev, buf, sizeof buf) != sizeof buf || !writeall(out, buf, sizeof buf)) goto done;
        for (unsigned i = 0; i < sizeof buf; ++i) crc = crc_table[(crc ^ buf[i]) & 255] ^ (crc >> 8);
    }
    hdr[2] = ~crc;
    if (s3(19, out, 0, 0) == 0 && writeall(out, hdr, sizeof hdr)) {
        closefd(out);
        closefd(dev);
        return;
    }
done:
    if (out >= 0) s3(10, reply, 0, 0);
    closefd(out);
    closefd(dev);
}

__attribute__((constructor)) static void backup_action(void) {
    uint32_t cookie = 0, index = 0;
    long fd;
    s3(10, stage, 0, 0);
    if (s3(39, scratch, 0700, 0) == 0) {
        if (!sys(21, (long)"tmpfs", (long)scratch, (long)"tmpfs", 6,
                 (long)"size=8m,mode=0700")) {
            fd = s3(5, owner, 1 | 64 | 128, 0600);
            if (fd >= 0 && writeall(fd, &tag, sizeof tag)) {
                closefd(fd);
                return;
            }
            closefd(fd);
            s3(52, scratch, 0, 0);
        }
        s3(40, scratch, 0, 0);
        return;
    }
    fd = s3(5, owner, 0, 0);
    if (fd < 0 || readall(fd, &cookie, sizeof cookie) != sizeof cookie || cookie != tag) {
        closefd(fd);
        return;
    }
    closefd(fd);
    fd = s3(5, request, 0, 0);
    if (fd < 0 || readall(fd, &index, sizeof index) != sizeof index) {
        closefd(fd);
        return;
    }
    closefd(fd);
    s3(10, request, 0, 0);
    if (index == 0xffffffffu) {
        s3(10, reply, 0, 0);
        s3(10, owner, 0, 0);
        if (!s3(52, scratch, 0, 0)) s3(40, scratch, 0, 0);
    } else {
        process(index);
    }
}
