#ifndef A7_FL_DIALOG_H
#define A7_FL_DIALOG_H
#include <stdint.h>
/* Install before SettingMenu construction; owns_root also accepts our clones.
 * Observes native draw/termination so no menu pointer outlives its view. */
int a7_fl_dialog_watch_menu(uintptr_t view2,void *manager,int (*owns_root)(const void*));
/* Returns zero after queuing the native dialog. commit returns zero only after
 * the preference transaction succeeds. Cancel never calls commit. */
int a7_fl_dialog_open(uintptr_t view2,void *manager,int (*commit)(void));
#endif
