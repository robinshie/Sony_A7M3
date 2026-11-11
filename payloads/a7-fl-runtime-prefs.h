/* Portable dual-slot preference records; caller owns durable file I/O. */
#ifndef A7_FL_RUNTIME_PREFS_H
#define A7_FL_RUNTIME_PREFS_H
#include <stdint.h>
#define A7_FL_RECORD_SIZE 128u
struct a7_fl_preference {
    uint32_t generation;
    int enabled;
    int parameters[8]; /* contrast,highlights,shadows,fade,saturation,sharpness,range,clarity */
    uint32_t candidate_crc;
};
/* SHA identifies immutable factory data; build is 24 bytes including padding.
 * Candidate CRC must match a table regenerated from these parameters at boot.
 */
int a7_fl_preference_encode(uint8_t [128],const struct a7_fl_preference *,
                            const uint8_t original_sha[32],const char build[24]);
int a7_fl_preference_decode(struct a7_fl_preference *,const uint8_t *,unsigned size,
                            const uint8_t original_sha[32],const char build[24]);
/* Returns selected slot 0/1, -1 for absent/invalid records, -2 for conflicting
 * valid records at the same generation. Invalid/torn inactive slot is ignored.
 * Do not interpret -1 as permission to overwrite pre-existing unknown files.
 */
int a7_fl_preference_choose(struct a7_fl_preference *,const uint8_t *,unsigned,
                            const uint8_t *,unsigned,const uint8_t [32],const char [24]);
#endif
