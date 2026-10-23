/* Monster Party's additions to the cycle host: developer coverage assists. */
#include "cyc_host_extras.h"
#include "mp_assist.h"
#include <string.h>

static void power_on(void *ctx) {(void)ctx;mp_assist_power_on();}
static void frame_begin(void *ctx) {(void)ctx;mp_assist_frame_begin();}
static void frame_end(void *ctx) {(void)ctx;mp_assist_frame_end();}
static bool option(void *ctx,const char *name,const char *value) {(void)ctx;return mp_assist_option(name,value);}

const CycHostExtras *cyc_host_extras(void) {
    static const CycHostOption options[]={
        {"--mp-assist",true,"life,foes: developer coverage assistance (refill life / clamp object HP)"},
        {"--mp-poke",true,"ADDR=VAL[@+FRAMES]: developer RAM fixture write before a frame (repeatable)"},
    };
    static const CycHostExtras extras={.power_on=power_on,.frame_begin=frame_begin,.frame_end=frame_end,
        .options=options,.option_count=sizeof options/sizeof options[0],.option=option};
    return &extras;
}
