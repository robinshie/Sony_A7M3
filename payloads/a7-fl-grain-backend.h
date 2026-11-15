/* User-process bridge to the exact embedded capture kernel module. */
#ifndef A7_FL_GRAIN_BACKEND_H
#define A7_FL_GRAIN_BACKEND_H
/* 0 = Off; presets 1..3, strength 0..9. Does not persist preferences. */
int a7_fl_grain_apply(unsigned preset,unsigned strength);
/* Film kernel only: one atomic selection for preset, grain and signed halo. */
int a7_fl_film_apply(unsigned preset,unsigned grain,int halation);
#endif
