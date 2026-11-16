#ifndef A7_FL_CUSTOM_TEXT_H
#define A7_FL_CUSTOM_TEXT_H
#include <stdint.h>
struct a7_custom_text_api {
 void (*text)(void*,const char*);
 const char *(*resolve)(uint32_t);
};
/* Owned PAS_MenuListCategorizedItem only. Seven embedded PAS_BtnPopup rows;
 * GEN_Label offsets are witnessed in original row setters and constructors.
 * Never traverse/cast arbitrary WidgetBase children as AppWidgetBase. */
int a7_custom_text_paint(const struct a7_custom_text_api*,void*);
#endif
