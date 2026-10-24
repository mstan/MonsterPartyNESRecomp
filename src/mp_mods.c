/* Optional player mods for the verified USA cartridge. Native instructions
 * remain original; cheats use keyed hooks and bank-qualified data reads.
 * Prototype Restoration 1.0 is Cubivore10's unmodified IPS, embedded at build
 * time and applied only after CRC and compiled-code dependency checks. */
#include "mp_mods.h"
#include "cyc_mod.h"
#include "mod_function_hooks.h"
#include "mod_runtime.h"
#include "mod_savestate.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mp_restoration_patch.h"

#define CHEATS "monster-party.cheats.game-genie"
#define RESTORE "monster-party.content.prototype-restoration"
static const char *const hooks[] = {
    "monster-party.cheat.invincible", "monster-party.cheat.enemies",
    "monster-party.cheat.guardians", "monster-party.cheat.bert"};
static uint32_t policy;
static int restore_requested;
static int state_registered;

static void fail(const char *message) {
    fprintf(stderr, "[Monster Party mods] %s\n", message);
    exit(EXIT_FAILURE);
}
static void set_hook(int i, int on) {
    if (!nes_mod_set_function_hook_enabled(hooks[i], on)) fail("Missing cheat hook.");
}
static void read_override(uint16_t addr, uint8_t old, uint8_t value) {
    if (!cyc_mod_set_prg_read_override(4u * 0x4000u + (addr & 0x3FFFu), old, value))
        fail("Cheat does not match this cartridge.");
}
static int choice(const char *feature, const char *option, const char *value) {
    char text[32];
    return nes_mod_option_value(CHEATS, feature, option, text, sizeof text) && !strcmp(text, value);
}
static int selected(const char *feature) { return nes_mod_feature_selected(CHEATS, feature); }
static int validate_policy(const uint8_t *in, int length) {
    uint32_t saved;
    if (!policy) return length == 0;
    if (!in || length != sizeof saved) return 0;
    memcpy(&saved, in, sizeof saved);
    return saved == policy;
}
static int save_policy(uint8_t *out, int capacity) {
    if (!policy) return 0;
    if (capacity < sizeof policy) return -1;
    memcpy(out, &policy, sizeof policy); return sizeof policy;
}
static int load_policy(const uint8_t *in, int length) { return validate_policy(in, length); }
static int invincible(uint16_t addr) { (void)addr; return 1; }
static int enemy_hit(uint16_t addr) {
    (void)addr;
    unsigned slot = cyc_mod_peek(0x38);
    if (slot < 12 && cyc_mod_peek((uint16_t)(0x3A8 + slot)))
        cyc_mod_poke((uint16_t)(0x3A8 + slot), 1);
    return 0;
}
static int guardian_hit(uint16_t addr) {
    (void)addr;
    unsigned slot = cyc_mod_peek(0x38);
    if (slot < 12 && cyc_mod_peek((uint16_t)(0x360 + slot)))
        cyc_mod_poke((uint16_t)(0x360 + slot), 1);
    return 0;
}
static int bert_timer(uint16_t addr) {
    (void)addr;
    if (cyc_mod_peek(0x5E) & 0x80) cyc_mod_poke(0x54, 0);
    return 0;
}
static void reset(void) {
    policy = 0; restore_requested = 0;
    for (int i = 0; i < 4; i++) set_hook(i, 0);
    cyc_mod_clear_rom_read_overrides();
}
static void activate_cheats(void) {
    /* Each selected feature names this callback through a unique plugin id.
     * Reapplying it is idempotent: overrides replace their physical offset. */
    if (selected("invincibility")) { set_hook(0, 1); policy |= 1u; }
    if (selected("one-hit")) {
        int enemies = !choice("one-hit", "targets", "guardians");
        int guardians = !choice("one-hit", "targets", "enemies");
        set_hook(1, enemies); set_hook(2, guardians);
        policy |= (uint32_t)(enemies | guardians << 1) << 1;
    }
    if (selected("endless-bert")) { set_hook(3, 1); policy |= 1u << 3; }
    if (selected("energy")) {
        int level = choice("energy", "amount", "super") ? 2 : choice("energy", "amount", "boosted") ? 1 : 0;
        if (level) {
            read_override(0x9532, 0x0C, level == 1 ? 0x18 : 0x2C);
            read_override(0x94C6, 0x0C, level == 1 ? 0x18 : 0x2C);
            policy |= (uint32_t)level << 4;
        }
    }
    if (selected("round")) {
        int round = nes_mod_get_option_int(CHEATS, "round", "number", 1);
        if (round < 1 || round > 8) fail("Invalid starting round.");
        if (round > 1) { read_override(0x954A, 0, (uint8_t)(round - 1)); policy |= (uint32_t)(round - 1) << 6; }
    }
    if (selected("speed")) {
        int speed = choice("speed", "amount", "4") ? 4 : choice("speed", "amount", "2") ? 2 : 1;
        if (speed > 1) {
            read_override(0x82CE, 0xFF, (uint8_t)(0u - speed));
            read_override(0x82B8, 1, (uint8_t)speed);
            policy |= (uint32_t)speed << 9;
        }
    }
    if (selected("jump")) {
        int height = choice("jump", "height", "extra") ? 2 : choice("jump", "height", "high") ? 1 : 0;
        if (height) {
            read_override(0x8555, 4, height == 1 ? 0x10 : 0x20);
            read_override(0x8556, 4, 0x10); read_override(0x8557, 4, 8);
            policy |= (uint32_t)height << 12;
        }
    }
    if (policy && !state_registered) {
        if (!nes_mod_register_savestate_hook("monster-party.cheats", save_policy, load_policy) ||
            !nes_mod_register_savestate_validator("monster-party.cheats", validate_policy))
            fail("Cannot register cheat save-state policy.");
        state_registered = 1;
    }
    if (policy) nes_mod_set_local_only("Monster Party cheats", 1);
}
static void activate_restoration(void) {
    restore_requested = 1;
    nes_mod_set_local_only("Prototype Restoration", 1);
}
static uint32_t crc32(const uint8_t *data, size_t size) {
    uint32_t crc = ~0u;
    for (size_t i = 0; i < size; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}
static int apply_ips(uint8_t *payload, size_t size) {
    const uint8_t *ips = mp_restoration_patch;
    size_t at = 5, end = sizeof mp_restoration_patch;
    if (end < 8 || memcmp(ips, "PATCH", 5)) return 0;
    while (at + 3 <= end) {
        if (!memcmp(ips + at, "EOF", 3)) return at + 3 == end;
        size_t offset = (size_t)ips[at] << 16 | (size_t)ips[at + 1] << 8 | ips[at + 2];
        at += 3;
        if (at + 2 > end) return 0;
        size_t count = (size_t)ips[at] << 8 | ips[at + 1]; at += 2;
        int run = !count;
        if (run) {
            if (at + 3 > end) return 0;
            count = (size_t)ips[at] << 8 | ips[at + 1]; at += 2;
        }
        /* The original IPS repeats the nine zero reserved bytes at 7..15.
         * They do not affect the payload or the verified cartridge geometry. */
        if (offset < 16) {
            if (offset != 7 || count != 9 || at + (run ? 1 : count) > end) return 0;
            for (size_t i = 0; i < count; i++) if (ips[at + (run ? 0 : i)]) return 0;
            at += run ? 1 : count; continue;
        }
        offset -= 16;
        if (!count || offset > size || count > size - offset || at + (run ? 1 : count) > end) return 0;
        if (run) { memset(payload + offset, ips[at++], count); }
        else { memcpy(payload + offset, ips + at, count); at += count; }
    }
    return 0;
}
void mp_mods_power_on(void) {
    if (restore_requested) {
        size_t size = cyc_mod_copy_cart_payload(NULL, 0);
        if (size != 0x40000) fail("Prototype Restoration requires the original USA cartridge.");
        uint8_t *payload = malloc(size);
        if (!payload) fail("Not enough memory for Prototype Restoration.");
        cyc_mod_copy_cart_payload(payload, size);
        uint32_t crc = crc32(payload, size);
        /* A soft restart may already have this exact data image. */
        if (crc != 0x71DB905Bu && (crc != 0x02B9E7C2u || !apply_ips(payload, size) ||
            crc32(payload, size) != 0x71DB905Bu || !cyc_mod_apply_cart_data_payload(payload, size))) {
            free(payload); fail("Prototype Restoration failed its cartridge/code safety check.");
        }
        free(payload);
        fprintf(stderr, "[Monster Party mods] Prototype Restoration 1.0 by Cubivore10\n");
    }
    nes_mod_lock_feature(RESTORE, "restoration");
}

NES_MOD_CONSTRUCTOR(mp_register_mods) {
    nes_mod_register_reset_callback(reset);
    const char *const plugins[] = {"invincibility", "one-hit", "endless-bert", "energy", "round", "speed", "jump"};
    for (int i = 0; i < 7; i++) {
        char id[96]; snprintf(id, sizeof id, "monster-party.cheats.%s", plugins[i]);
        nes_mod_register_activation_plugin(id, activate_cheats);
    }
    nes_mod_register_activation_plugin("monster-party.prototype-restoration", activate_restoration);
    nes_mod_register_function_entry_plugin(hooks[0], 0x879A, invincible);
    nes_mod_register_function_entry_plugin(hooks[1], 0x8502, enemy_hit);
    nes_mod_register_function_entry_plugin(hooks[2], 0x8D22, guardian_hit);
    nes_mod_register_function_entry_plugin(hooks[3], 0x804A, bert_timer);
}
