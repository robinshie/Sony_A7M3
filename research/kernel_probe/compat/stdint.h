#ifndef A7_KERNEL_STDINT_H
#define A7_KERNEL_STDINT_H
#include <linux/types.h>
#define UINT32_MAX ((uint32_t)~0U)
#define UINTPTR_MAX ((uintptr_t)~0UL)
#ifndef SIZE_MAX
#define SIZE_MAX ((size_t)~0UL)
#endif
#endif
