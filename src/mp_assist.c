/* Developer assists for Monster Party coverage routes (USA, payload 02B9E7C2).
 *
 * These are host-side RAM writes, the cycle-backend equivalent of the RAM
 * fixtures the NES coverage campaign journals into save states. They never
 * patch guest code, are off unless a --mp-* option asks for them, and print
 * every one-shot write so a route's evidence records its assistance.
 * Addresses are verified against the original code:
 *   $97      round - 1            (4:$954F new game, 4:$943B level init)
 *   $9E      Mark's life          (4:$9531 starts at $0C, 4:$87A7 DEC on a hit)
 *   $58      guardians left       (4:$9447 from the per-round table at $945B)
 *   $38      running task slot    (7:$C103 scheduler over 12 slots, $0300,X < $80 = live)
 *   $0360,X  guardian hit points  (5:$8D22 subtracts 1 or 3 and floors at 0)
 */
#include "mp_assist.h"
#include "cyc_mod.h"
#include "mod_function_hooks.h"
#include "mod_runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define GUARDIAN_HIT_HOOK "monster-party.assist.guardian-hit"
#define MAX_POKES 64
typedef struct { unsigned frame; uint16_t addr; uint8_t value; } Poke;
static Poke pokes[MAX_POKES];
static unsigned poke_count, frames_run, guardian_hits;
static int refill_life, weak_guardians;
static FILE *ram_log;
static void close_ram_log(void) {if(ram_log)fclose(ram_log);ram_log=NULL;}

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

static void poke(uint16_t addr, uint8_t value, const char *why) {
    uint8_t before = cyc_mod_peek(addr);
    if (before == value) return;
    cyc_mod_poke(addr, value);
    if (why) printf("mp-assist: frame +%u %s $%04X %02X -> %02X\n", frames_run, why, addr, before, value);
}

/* At 5:$8D22, the routine that applies one landed hit to the guardian in task
 * slot $38: leave it one point, so the game's own subtraction and defeat path
 * run on this hit (the "one hit kills guardians" cheat, without a ROM patch). */
static int guardian_hit(uint16_t addr) {
    (void)addr;
    uint8_t slot = cyc_mod_peek(0x38);
    if (slot < 12 && cyc_mod_peek((uint16_t)(0x360 + slot)) > 1) {
        guardian_hits++;
        poke((uint16_t)(0x360 + slot), 1, "guardian-hit");
    }
    return 0;
}

static void arm(void) {
    if (weak_guardians && !nes_mod_set_function_hook_enabled(GUARDIAN_HIT_HOOK, 1)) {
        fprintf(stderr, "mp-assist: hook %s is not declared by this program\n", GUARDIAN_HIT_HOOK);
        exit(2);
    }
}

bool mp_assist_option(const char *name, const char *value) {
    if (!strcmp(name, "--mp-poke")) return parse_poke(value);
    if (!strcmp(name, "--mp-ram-log")) {
        /* 2 KiB of CPU RAM per frame, appended after each frame: exploration evidence. */
        ram_log = fopen(value, "wb");
        if (ram_log) atexit(close_ram_log);
        return ram_log != NULL;
    }
    if (!strcmp(name, "--mp-assist")) {
        char list[128];
        snprintf(list, sizeof list, "%s", value);
        for (char *t = strtok(list, ","); t; t = strtok(NULL, ",")) {
            if (!strcmp(t, "life")) refill_life = 1;
            else if (!strcmp(t, "guardians")) weak_guardians = 1;
            else return false;
        }
        arm();
        return true;
    }
    return false;
}

void mp_assist_frame_begin(void) {
    for (unsigned i = 0; i < poke_count; i++)
        if (pokes[i].frame == frames_run) poke(pokes[i].addr, pokes[i].value, "poke");
}

void mp_assist_frame_end(void) {
    /* Silent per-frame assist: the run header records that it was on. */
    if (refill_life) poke(0x9E, 0x0C, NULL);
    if (ram_log) {
        uint8_t ram[0x800];
        for (unsigned a = 0; a < sizeof ram; a++) ram[a] = cyc_mod_peek((uint16_t)a);
        fwrite(ram, 1, sizeof ram, ram_log);
    }
    frames_run++;
}

void mp_assist_power_on(void) {
    frames_run = guardian_hits = 0;
    arm();
    if (refill_life || weak_guardians || poke_count)
        printf("mp-assist: life=%d guardians=%d pokes=%u (developer coverage assistance)\n", refill_life, weak_guardians, poke_count);
}

NES_MOD_CONSTRUCTOR(register_coverage_assists) {
    nes_mod_register_function_entry_plugin(GUARDIAN_HIT_HOOK, 0x8D22, guardian_hit);
}
