#pragma once
/* Monster Party adaptive widescreen (experimental, opt-in): mp_widescreen.c. */
#include <stdbool.h>
#include <stddef.h>
#include "cyc_host_extras.h"

extern const CycHostOption mp_ws_options[];
extern const size_t mp_ws_option_count;
bool mp_ws_option(const char *name, const char *value);
void mp_ws_power_on(void);
void mp_ws_frame_end(void);
void mp_ws_tcp_setup(void);
