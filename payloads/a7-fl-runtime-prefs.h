/* Portable dual-slot preference records; caller owns durable file I/O. */
#ifndef A7_FL_RUNTIME_PREFS_H
#define A7_FL_RUNTIME_PREFS_H
#include <stdint.h>
#define A7_FL_RECORD_SIZE 128u
enum a7_fl_preset { A7_FL_PRESET_OFF=0, A7_FL_PRESET_FL=1, A7_FL_PRESET_CINEMA=2, A7_FL_PRESET_LEICA=3 };
#ifdef A7_FL_LEICA_LOOK
#define A7_FL_PRESET_MAX A7_FL_PRESET_LEICA
#elif defined(A7_FL_DUAL_LOOK)
#define A7_FL_PRESET_MAX A7_FL_PRESET_CINEMA
#else
#define A7_FL_PRESET_MAX A7_FL_PRESET_FL
#endif
static inline int a7_fl_preset_valid(int preset) {return preset>=0 && preset<=A7_FL_PRESET_MAX;}
struct a7_fl_preference {
    uint32_t generation;
    int enabled; /* Historical field: now the preset enum; 0/1 remain byte-compatible. */
    int parameters[8]; /* contrast,highlights,shadows,fade,saturation,sharpness,range,clarity */
    uint32_t candidate_crc;
    /* Schema 0 is the legacy shared bank. Schema 2 stores the other look's
     * signed-byte controls in the eight formerly reserved record bytes.
     * Off uses the FL bank; switching FL2 <-> Off/FL exchanges the banks. */
    uint32_t schema;
    int8_t other_parameters[8];
    int8_t third_parameters[8]; /* Schema 3: inactive banks, sorted by preset ID. */
#ifdef A7_FL_FILM_CONTROLS
    /* Schema 4: explicit FL/FL2/FL3 banks, unaffected by active-bank exchange.
     * Each bank: grain, halation, black, shadow, midtone, highlight, white.
     * Serialized as signed five-bit values alongside the original controls. */
    int8_t film[3][7];
#endif
};
void a7_fl_preference_switch(struct a7_fl_preference *,int preset);
int a7_fl_preference_migrate(struct a7_fl_preference *);
int a7_fl_preference_migrate_three(struct a7_fl_preference *);
#ifdef A7_FL_FILM_CONTROLS
int a7_fl_preference_migrate_film(struct a7_fl_preference *);
#endif
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
