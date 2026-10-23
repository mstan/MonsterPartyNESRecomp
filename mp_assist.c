/* Developer assists for Monster Party coverage routes (USA, payload 02B9E7C2).
 *
 * These are host-side RAM writes between frames, the cycle-backend equivalent
 * of the RAM fixtures the NES coverage campaign journals into save states. They
 * never patch guest code, are off unless a --mp-* option asks for them, and
 * print every write they make so a route's evidence records its assistance.
 * Addresses are verified against the original bank-4/5 code:
 *   $97      round - 1          (4:$954F new game, 4:$943B level init)
 *   $9E      Mark's life        (4:$9531 starts at $0C, 4:$87A7 DEC on a hit)
 *   $58      guardians left     (4:$9447 from the per-round table at $945B)
 *   $03A8,X  object hit points  (5:$8502 SBC damage)
 */
#include "mp_assist.h"
#include "cyc_mod.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_POKES 64
typedef struct { unsigned frame; uint16_t addr; uint8_t value; } Poke;
static Poke pokes[MAX_POKES];
static unsigned poke_count, frames_run;
static int refill_life, weaken_foes;

static bool parse_poke(const char *s) {
    /* ADDR=VALUE[@+FRAMES], hex address and value; FRAMES counts this process's frames. */
    unsigned addr, value, frame = 0;
    char tail[16] = "";
    if (poke_count >= MAX_POKES || sscanf(s, "%x=%x%15s", &addr, &value, tail) < 2) return false;
    if (tail[0] && sscanf(tail, "@+%u", &frame) != 1) return false;
    if (addr > 0x7FF || value > 255) return false;
    pokes[poke_count++] = (Poke){frame, (uint16_t)addr, (uint8_t)value};
    return true;
}

bool mp_assist_option(const char *name, const char *value) {
    if (!strcmp(name, "--mp-poke")) return parse_poke(value);
    if (!strcmp(name, "--mp-assist")) {
        char list[128];
        snprintf(list, sizeof list, "%s", value);
        for (char *t = strtok(list, ","); t; t = strtok(NULL, ",")) {
            if (!strcmp(t, "life")) refill_life = 1;
            else if (!strcmp(t, "foes")) weaken_foes = 1;
            else return false;
        }
        return true;
    }
    return false;
}

static void poke(uint16_t addr, uint8_t value, const char *why) {
    uint8_t before = cyc_mod_peek(addr);
    if (before == value) return;
    cyc_mod_poke(addr, value);
    if (why) printf("mp-assist: frame +%u %s $%04X %02X -> %02X\n", frames_run, why, addr, before, value);
}

void mp_assist_frame_begin(void) {
    for (unsigned i = 0; i < poke_count; i++)
        if (pokes[i].frame == frames_run) poke(pokes[i].addr, pokes[i].value, "poke");
}

void mp_assist_frame_end(void) {
    /* Silent per-frame assists: the run header records that they were on. */
    if (refill_life) poke(0x9E, 0x0C, NULL);
    if (weaken_foes)
        for (uint16_t x = 0; x < 12; x++)
            if (cyc_mod_peek(0x3A8 + x) > 1) poke(0x3A8 + x, 1, NULL);
    frames_run++;
}

void mp_assist_power_on(void) {
    frames_run = 0;
    if (refill_life || weaken_foes || poke_count)
        printf("mp-assist: life=%d foes=%d pokes=%u (developer coverage assistance)\n", refill_life, weaken_foes, poke_count);
}
