#ifndef A7_FL_SD_RECIPE_H
#define A7_FL_SD_RECIPE_H

#include "a7-fl-runtime-prefs.h"

#ifndef A7_FL_SIX_LOOKS
#error "SD recipes require six look banks"
#endif

/* Pure overlay: -1 invalid, 0 unchanged, 1 changed. Does not save or switch looks. */
int a7_fl_sd_recipe_name(const char *);
int a7_fl_sd_recipe_apply(const unsigned char *, unsigned,
                         const struct a7_fl_preference *,
                         struct a7_fl_preference *);
#endif
