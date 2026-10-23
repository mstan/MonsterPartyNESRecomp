/* Monster Party's additions to the cycle host: developer coverage assists and
 * the opt-in adaptive widescreen mod (mp_widescreen.c). */
#include "cyc_host_extras.h"
#include "mp_assist.h"
#include "mp_widescreen.h"
#include <string.h>

static void power_on(void *ctx) {(void)ctx;mp_assist_power_on();mp_ws_power_on();}
static void frame_begin(void *ctx) {(void)ctx;mp_assist_frame_begin();}
static void frame_end(void *ctx) {(void)ctx;mp_assist_frame_end();mp_ws_frame_end();}
static bool option(void *ctx,const char *name,const char *value) {
    (void)ctx;
    return !strncmp(name,"--widescreen",12)?mp_ws_option(name,value):mp_assist_option(name,value);
}
static void tcp_setup(void *ctx) {(void)ctx;mp_ws_tcp_setup();}

const CycHostExtras *cyc_host_extras(void) {
    static const CycHostOption assist_options[]={
        {"--mp-assist",true,"life,guardians: developer coverage assistance (refill life / guardians fall to the next hit)"},
        {"--mp-ram-log",true,"FILE: CPU RAM after every frame (2 KiB records), developer exploration"},
        {"--mp-poke",true,"ADDR=VAL[@+FRAMES]: developer RAM fixture write before a frame (repeatable)"},
    };
    enum {ASSIST=sizeof assist_options/sizeof assist_options[0]};
    static CycHostOption options[ASSIST+8];
    static CycHostExtras extras={.power_on=power_on,.frame_begin=frame_begin,.frame_end=frame_end,
        .options=options,.option=option,.tcp_setup=tcp_setup};
    if(!extras.option_count) {
        memcpy(options,assist_options,sizeof assist_options);
        for(size_t i=0;i<mp_ws_option_count && ASSIST+i<sizeof options/sizeof options[0];i++)options[ASSIST+i]=mp_ws_options[i];
        extras.option_count=ASSIST+mp_ws_option_count;
    }
    return &extras;
}
