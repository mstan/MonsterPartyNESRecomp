/* Optional developer build only. Exercise original cartridge routines through
 * the real native/interpreter scheduler; every probe restores the full machine. */
#include "cyc_mod.h"
#include <stdio.h>
#include <stdlib.h>

static int call(int bank, unsigned routine) {
    const uint8_t stub[] = {0xA9,0x80,0x8D,0x00,0x80,0xA9,(uint8_t)bank,0x20,0x0D,0xC6,
        0xA2,0x06,0xA0,0x00,0x20,(uint8_t)routine,(uint8_t)(routine>>8),0x60};
    for (unsigned i=0;i<sizeof stub;i++) cyc_mod_poke((uint16_t)(0x700+i),stub[i]);
    CycModRegs r={0,6,0,0xFD,0x24,0};
    return cyc_mod_call(0x700,&r);
}
static void begin(void) {
    if (!cyc_mod_isolate_begin()) abort();
    cyc_mod_allow_isolated_hooks(true);
}
void mp_mods_probe(void) {
    unsigned life,enemy,dead,guardian,bert,timer;
    begin();
    cyc_mod_poke(0x9E,12);cyc_mod_poke(0x52,0);
    if (!call(4,0x879A)) abort();
    life=cyc_mod_peek(0x9E);cyc_mod_isolate_end();
    begin();
    cyc_mod_poke(0x38,6);cyc_mod_poke(0x10,1);
    cyc_mod_poke(0x3AE,3);cyc_mod_poke(0x336,0);
    if (!call(5,0x8502)) abort();
    enemy=cyc_mod_peek(0x3AE);dead=!!(cyc_mod_peek(0x336)&2);cyc_mod_isolate_end();
    begin();
    cyc_mod_poke(0x38,6);cyc_mod_poke(0x97,0);cyc_mod_poke(0x3E1,0);cyc_mod_poke(0x366,5);
    if (!call(5,0x8D22)) abort();
    guardian=cyc_mod_peek(0x366);cyc_mod_isolate_end();
    begin();
    cyc_mod_poke(0x5E,0x80);cyc_mod_poke(0x54,0x27);cyc_mod_poke(0x37,1);
    if (!call(4,0x803B)) abort();
    bert=cyc_mod_peek(0x5E);timer=cyc_mod_peek(0x54);cyc_mod_isolate_end();
    printf("mod-probe: life=%u enemy_hp=%u enemy_dead=%u guardian_hp=%u bert=%u timer=%u\n",
           life,enemy,dead,guardian,bert,timer);
}
