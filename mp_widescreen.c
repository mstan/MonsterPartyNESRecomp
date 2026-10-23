/* Monster Party (USA, payload 02B9E7C2): opt-in adaptive widescreen for the
 * cycle host. Package monster-party.enhancement.widescreen (default off).
 *
 * Everything here reads or replays the original program; no guest code is
 * patched. Addresses are verified against the USA ROM (tools/dis6502.py) and
 * by runtime measurement (WIDESCREEN.md):
 *
 * Level map (fixed bank, scroll task 7:$D6DC .. $D808):
 *   $40        PRG bank holding the area's data (7:$D414, mapped by 7:$D775)
 *   $50/$25    camera page / pixel; $51 page offset into the area's pages
 *   $032E      last camera page (7:$D6E4 stops scrolling there)
 *   ($62)+(page+$51)*16   page record: 8 x (column id, attribute id)  7:$D7C2
 *   ($60)+id*24           column: two 16-pixel halves x 12 metatiles    7:$D848/$D775
 *   ($66)+metatile*4      tiles TL, TR, BL, BR                          7:$D834/$D7A6
 *   ($64)+id*6            attribute bytes for rows 0-5 (32 px each)     7:$D808/$D7E7
 *   The playfield is lines 0-191; Y scroll is always 0 (only 4:$92E1 and
 *   7:$C274 write $26). The status bar is nametable 0 rows 24-29 after the
 *   sprite-0 split in 7:$C016, with CHR banks $42/$41 instead of $3C/$3D.
 * Objects: $03C0+i active, $03CB/$03D6/$040D Y / screen X / screen X page
 *   (i = 0..10); 7:$C699 draws object Y into the OAM buffer from offset $18
 *   through 7:$C565, which hides a piece whose 16-bit X is off page 0. 7:$C728
 *   builds the buffer once per frame; the NMI DMAs it at 7:$C20D.
 * Spawning (viewport option): 7:$DB4B spawns the enemy authored for the
 *   16-pixel column just scrolled in (table ($71), index (page+$51)*16 +
 *   X/16) into objects 6-8; 5:$82EF and 5:$8306 despawn an object further
 *   than 16 / 64 pixels outside the screen.
 */
#include "mp_widescreen.h"
#include "cyc_core.h"
#include "cyc_mod.h"
#include "cyc_render.h"
#include "cyc_run.h"
#include "cyc_session.h"
#include "cyc_tcp.h"
#include "cyc_video.h"
#include "mod_function_hooks.h"
#include "mod_runtime.h"
#include "mod_savestate.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define R(a) cyc_mod_peek((uint16_t)(a))
#define W(a, v) cyc_mod_poke((uint16_t)(a), (uint8_t)(v))
#define WS_PACKAGE "monster-party.enhancement.widescreen"
#define WS_PLUGIN "monster-party.widescreen"
#define PF_LINES 192          /* playfield lines; the status bar follows */
#define STUB 0x0700           /* scratch CPU RAM for isolated bank-mapping stubs */
#define MAX_PIECES 256
#define MAX_REACH (CYC_VIDEO_MAX_WIDTH + 128) /* anchored views can put the whole margin on one side */

enum { H_DRAW, H_OAM, H_DMA, H_SPAWN, H_CULL16, H_CULL64, H_COUNT };
static const char *const hook_ids[H_COUNT] = {
    "monster-party.widescreen.draw", "monster-party.widescreen.oam-build", "monster-party.widescreen.dma",
    "monster-party.widescreen.spawn", "monster-party.widescreen.cull16", "monster-party.widescreen.cull64"};
static const uint16_t hook_addrs[H_COUNT] = {0xC699, 0xC728, 0xC20D, 0xDB4B, 0x82EF, 0x8306};

/* ---- presentation state (saved with cycle states) ---- */
typedef struct { int16_t x; uint8_t y, tile, attr, pad; } Piece;   /* x: signed screen X */
typedef struct {
    uint32_t magic;                   /* 'MPW1' */
    uint16_t build_count, display_count;
    uint8_t building, pad[3];
    Piece build[MAX_PIECES], display[MAX_PIECES];
    uint8_t ledger[256];              /* viewport: spawn columns activated in the wide view */
} WsState;
#define WS_MAGIC 0x3157504Du
static WsState ws;

/* ---- settings ---- */
static int enabled, viewport = 1, anchored = 1, aspect = NES_VIDEO_FIT;
static FILE *report;
static uint64_t report_frame;

/* ---- diagnostics ---- */
static uint64_t failures, captures, overflow, spawns, retains, culls, suppressed;
static int map_samples, map_errors, last_origin, last_scene;

/* ---- ROM caches (PRG/CHR ROM never change) ---- */
static uint8_t prg[8][0x4000], chr[32][0x1000];
static uint8_t prg_ok[8], chr_ok[32];

static int unwrap(int captured, int expected, int period)
{
    int delta = (captured - expected + period / 2) % period;
    if (delta < 0) delta += period;
    return expected + delta - period / 2;
}

/* Inside an isolated scope: run a tiny stub from CPU RAM (MMC1 reset, then
 * the game's own bank-select routine with A = value). */
static bool run_map_stub(uint16_t routine, uint8_t value)
{
    const uint8_t code[] = {0xA9, 0x80, 0x8D, 0x00, 0x80, 0xA9, value, 0x20, (uint8_t)routine, (uint8_t)(routine >> 8), 0x60};
    for (size_t i = 0; i < sizeof code; i++) W(STUB + i, code[i]);
    CycModRegs regs;
    cyc_mod_regs(&regs);
    return cyc_mod_call(STUB, &regs);
}

static bool cache_prg(int bank)
{
    bank &= 7;
    if (prg_ok[bank]) return true;
    if (bank == 7) {
        for (int i = 0; i < 0x4000; i++) prg[7][i] = R(0xC000 + i);
        return prg_ok[7] = 1;
    }
    if (cyc_mod_isolated() || !cyc_mod_isolate_begin()) return false;
    bool ok = run_map_stub(0xC60D, (uint8_t)bank);     /* 7:$C60D: PRG bank at $8000 */
    if (ok) for (int i = 0; i < 0x4000; i++) prg[bank][i] = R(0x8000 + i);
    cyc_mod_isolate_end();
    if (!ok) failures++;
    return prg_ok[bank] = ok;
}

static bool cache_chr(int bank)
{
    bank &= 31;
    if (chr_ok[bank]) return true;
    if (cyc_mod_isolated() || !cyc_mod_isolate_begin()) return false;
    bool ok = run_map_stub(0xC5E5, (uint8_t)bank);     /* 7:$C5E5: CHR bank 0 ($0000) */
    if (ok) for (int i = 0; i < 0x1000; i++) chr[bank][i] = cyc_render_chr((uint16_t)i);
    cyc_mod_isolate_end();
    if (!ok) failures++;
    return chr_ok[bank] = ok;
}

static uint8_t rom(int bank, uint16_t addr)
{
    return addr >= 0xC000 ? prg[7][addr - 0xC000] : prg[bank & 7][addr & 0x3FFF];
}

/* ---- scene ---- */
enum { SCENE_NONE, SCENE_ROOM, SCENE_SCROLL };
static int ptr(int a) { return R(a) | R(a + 1) << 8; }
static int scene(void)
{
    /* $31: the status-bar split runs; $0449: object sprites are composed;
     * ($62): an area's page table is loaded (zero on the round card). */
    if (!R(0x31) || !R(0x449) || !ptr(0x62) || !ptr(0x60) || !ptr(0x64) || !ptr(0x66)) return SCENE_NONE;
    /* Guardian arenas keep their native, centered composition even when an
     * arena's loaded map has more than one page. The HUD has its own origin. */
    return R(0x32E) && !(R(0x52) & 0x80) ? SCENE_SCROLL : SCENE_ROOM;
}
static int world_width(void) { return (R(0x32E) + 1) * 256; }
static int game_camera(void) { return R(0x50) * 256 + R(0x25); }

typedef struct { int bank, p60, p62, p64, p66, offset, width; uint8_t b0, b1, h0, h1; } Level;
static bool level_now(Level *l)
{
    l->bank = R(0x40) & 7;
    l->p60 = ptr(0x60); l->p62 = ptr(0x62); l->p64 = ptr(0x64); l->p66 = ptr(0x66);
    l->offset = R(0x51); l->width = world_width();
    l->b0 = R(0x3C); l->b1 = R(0x3D); l->h0 = R(0x42); l->h1 = R(0x41);
    return cache_prg(7) && cache_prg(l->bank) && cache_chr(l->b0) && cache_chr(l->b1) && cache_chr(l->h0) &&
           cache_chr(l->h1);
}

/* The background tile and palette at world pixel (wx, y), y < 192. */
static bool decode(const Level *l, int wx, int y, int *tile, int *pal)
{
    if (wx < 0 || wx >= l->width || y < 0 || y >= PF_LINES) return false;
    int page = ((wx >> 8) + l->offset) & 0xFF, col = (wx & 255) >> 5;
    uint16_t rec = (uint16_t)(l->p62 + page * 16 + col * 2);
    uint8_t cid = rom(l->bank, rec), aid = rom(l->bank, (uint16_t)(rec + 1));
    uint8_t mt = rom(l->bank, (uint16_t)(l->p60 + cid * 24 + ((wx >> 4) & 1) * 12 + (y >> 4)));
    *tile = rom(l->bank, (uint16_t)(l->p66 + mt * 4 + ((y >> 3) & 1) * 2 + ((wx >> 3) & 1)));
    uint8_t attr = rom(l->bank, (uint16_t)(l->p64 + aid * 6 + (y >> 5)));
    *pal = (attr >> (((y >> 4) & 1) * 4 + ((wx >> 4) & 1) * 2)) & 3;
    return true;
}

static uint8_t chr_byte(uint8_t b0, uint8_t b1, uint16_t addr)
{
    return addr < 0x1000 ? chr[b0 & 31][addr] : chr[b1 & 31][addr & 0xFFF];
}
static void line_banks(const Level *l, int y, uint8_t *b0, uint8_t *b1)
{
    *b0 = y < PF_LINES ? l->b0 : l->h0;
    *b1 = y < PF_LINES ? l->b1 : l->h1;
}
static int tile_pixel(const Level *l, int y, uint16_t table, int tile, int row, int bit)
{
    uint8_t b0, b1;
    line_banks(l, y, &b0, &b1);
    uint16_t a = (uint16_t)(table + tile * 16 + row);
    return ((chr_byte(b0, b1, a) >> bit) & 1) | (((chr_byte(b0, b1, (uint16_t)(a + 8)) >> bit) & 1) << 1);
}

/* ---- sprite packets ---- */
static void begin_build(void) { ws.build_count = 0; ws.building = 1; }

static void capture_object(void)
{
    CycModRegs regs;
    cyc_mod_regs(&regs);
    int obj = regs.y;
    if (obj > 10) return;
    int x16 = (int16_t)(uint16_t)(R(0x40D + obj) << 8 | R(0x3D6 + obj));
    if (x16 < -MAX_REACH || x16 >= 256 + MAX_REACH) return;
    if (!cyc_mod_isolate_begin()) return;
    /* The game's own drawer, with the object moved to the middle of page 0 so
     * no piece is hidden; each piece then moves back by the same amount. */
    W(0x3D6 + obj, 0x80);
    W(0x40D + obj, 0);
    uint8_t start = R(0x18);
    bool ok = cyc_mod_call(0xC699, &regs);
    if (ok) {
        uint8_t end = R(0x18);
        for (unsigned i = start, n = 0; i != end && n < 64; i = (i + 4) & 0xFF, n++) {
            uint8_t y = R(0x200 + i);
            if (y >= 0xEF) continue;
            if (ws.build_count >= MAX_PIECES) { overflow++; break; }
            Piece *p = &ws.build[ws.build_count++];
            p->x = (int16_t)(x16 - 0x80 + R(0x203 + i));
            p->y = y; p->tile = R(0x201 + i); p->attr = R(0x202 + i); p->pad = 0;
        }
    }
    cyc_mod_isolate_end();
    if (ok) captures++; else failures++;
}

static void latch_packets(void)
{
    if (!ws.building) return;       /* no OAM was composed since the last DMA */
    memcpy(ws.display, ws.build, sizeof ws.build);
    ws.display_count = ws.build_count;
    ws.build_count = 0;
    ws.building = 0;
}

/* ---- viewport activation ---- */
static int anchored_origin(int width, int cam, int lw);
static int margin_left(void)
{
    int w = cyc_video_width();
    if (w <= 256) return 0;
    /* Simulation must not depend on whether the host composed a picture this
     * frame (headless captures, skipped presentation, or a slow display). */
    return anchored && scene() == SCENE_SCROLL ? anchored_origin(w, game_camera(), world_width()) : (w - 256) / 2;
}
static int margin_right(void) { int w = cyc_video_width(); return w > 256 ? w - 256 - margin_left() : 0; }

static int spawn_index(int wx, int offset) { return ((((wx >> 8) + offset) & 0x0F) << 4) | ((wx & 0xFF) >> 4); }

/* Spawn the authored enemy of world column wx (16-aligned) through 7:$DB4B
 * on an isolated machine whose camera puts that column at the routine's
 * native edge; commit only what the routine changed and move the new object
 * back by the projection. */
static bool spawn_column(int wx, int dir, int cam)
{
    int proj = dir ? wx - 256 : wx;               /* camera whose leading column is wx */
    proj = (proj & ~15) | (cam & 15);
    if (proj < 0 || (proj >> 8) > 255) return false;
    if (!cyc_mod_isolate_begin()) return false;
    static uint8_t before[0x800];
    memcpy(before, cyc_cpu_ram(), sizeof before);
    W(0x25, proj & 0xFF);
    W(0x50, proj >> 8);
    W(0x521, (R(0x521) & 0xFE) | dir);
    W(0x33A, R(0x33A) | 0x80);
    CycModRegs regs;
    cyc_mod_regs(&regs);
    bool ok = cyc_mod_call(0xDB4B, &regs);
    static uint8_t after[0x800];
    if (ok) memcpy(after, cyc_cpu_ram(), sizeof after);
    cyc_mod_isolate_end();
    if (!ok) { failures++; return false; }
    int slot = -1;
    for (int k = 0; k < 3; k++)
        if (!(before[0x3C6 + k] & 0x80) && (after[0x3C6 + k] & 0x80)) slot = k;
    if (slot < 0) return false;
    /* Object fields and task slots only: no camera, scratch or stack bytes. */
    for (int a = 0x200; a < 0x800; a++)
        if (a != 0x33A && before[a] != after[a]) W(a, after[a]);
    int obj = 6 + slot;
    int x16 = (int16_t)(uint16_t)(after[0x40D + obj] << 8 | after[0x3D6 + obj]) + (proj - cam);
    W(0x3D6 + obj, x16 & 0xFF);
    W(0x40D + obj, (x16 >> 8) & 0xFF);
    spawns++;
    return true;
}

static void viewport_spawn(void)
{
    if (!viewport || scene() != SCENE_SCROLL || cyc_video_width() <= 256) return;
    if (R(0x52) & 0x80) return;     /* 7:$D4BB: guardian/boss areas keep their own spawning */
    int cam = game_camera(), offset = R(0x51), wl = margin_left(), wr = margin_right(), width = world_width();
    int table = ptr(0x71);
    /* Columns the wide view shows beyond the native edges' own spawn columns. */
    for (int pass = 0; pass < 2; pass++) {
        int from = pass ? ((cam + 256 + 16) & ~15) + 16 : ((cam - wl) & ~15);
        int to = pass ? cam + 256 + wr : (cam & ~15) - 16;
        for (int wx = from; wx < to; wx += 16) {
            if (wx < 0 || wx >= width) continue;
            int idx = spawn_index(wx, offset);
            if (ws.ledger[idx] || !R(table + idx)) continue;
            /* Leave room for the column the native edge is about to reach. */
            if (spawn_column(wx, pass, cam)) ws.ledger[idx] = 1;
            else {
                /* No free slot (or it is already alive from this column). */
                bool alive = false;
                for (int k = 0; k < 3; k++)
                    alive |= (R(0x3C6 + k) & 0x80) && R(0x408 + k) == idx;
                if (alive) ws.ledger[idx] = 1;
            }
        }
    }
}

static void viewport_forget(void)
{
    if (!viewport || scene() != SCENE_SCROLL) { memset(ws.ledger, 0, sizeof ws.ledger); return; }
    int cam = game_camera(), offset = R(0x51), wl = margin_left(), wr = margin_right();
    bool keep[256] = {0};
    for (int wx = (cam - wl - 16) & ~15; wx < cam + 256 + wr + 16; wx += 16)
        if (wx >= 0) keep[spawn_index(wx, offset)] = true;
    for (int i = 0; i < 256; i++)
        if (!keep[i]) ws.ledger[i] = 0;
}

/* 7:$DB4B entry: the native column spawn. A column already activated by the
 * wide view keeps that activation (no second enemy at the 4:3 edge). */
static int hook_spawn(void)
{
    if (!viewport || scene() != SCENE_SCROLL || cyc_video_width() <= 256) return 0;
    if (R(0x33A) & 0x80) {
        int dir = R(0x521) & 1, page = (dir + R(0x50)) & 0xFF;
        if (!(page & 0x80)) {
            int idx = ((((page + R(0x51)) & 0x0F) << 4) | (R(0x25) >> 4));
            if (ws.ledger[idx]) {
                W(0x33A, R(0x33A) & 0x7F);
                suppressed++;
                return 1;
            }
        }
    }
    viewport_spawn();
    return 0;
}

/* 5:$82EF / 5:$8306 entry: keep objects inside the wide view (plus the
 * routine's own 16 / 64 pixel allowance); despawn the rest, including pages
 * the native byte test cannot tell apart at 32:9. */
static int hook_cull(int reach)
{
    if (!viewport || scene() != SCENE_SCROLL || cyc_video_width() <= 256) return 0;
    int obj = R(0x3A);
    if (obj > 10) return 0;
    int x16 = (int16_t)(uint16_t)(R(0x40D + obj) << 8 | R(0x3D6 + obj));
    if (x16 >= -margin_left() - reach && x16 < 256 + margin_right() + reach) {
        if (x16 < -reach || x16 >= 256 + reach) retains++;
        return 1;
    }
    W(0x3D6 + obj, 0x80);
    W(0x40D + obj, 1);          /* a page the native test despawns */
    culls++;
    return 0;
}

static int hook(uint16_t addr)
{
    if (!enabled) return 0;
    switch (addr) {
    case 0xC728: if (R(0x449)) begin_build(); return 0;
    case 0xC699: capture_object(); return 0;
    case 0xC20D: latch_packets(); return 0;
    case 0xDB4B: return hook_spawn();
    case 0x82EF: return hook_cull(16);
    case 0x8306: return hook_cull(64);
    }
    return 0;
}

/* ---- compositor ---- */
static uint8_t coverage[CYC_VIDEO_MAX_WIDTH * 240];

static void draw_piece(uint32_t *out, int width, const Level *l, int ox, const Piece *p, bool native_hidden, int x0)
{
    int sy = p->y + 1;
    if (sy >= 240) return;
    bool tall = cyc_render_line_sprite16(sy < 239 ? sy : 239);
    int rows = tall ? 16 : 8;
    for (int r = 0; r < rows; r++) {
        int y = sy + r;
        if (y >= 240 || !(cyc_render_line_mask(y) & 16)) continue;
        int row = (p->attr & 0x80) ? rows - 1 - r : r;
        uint16_t pattern = tall ? (uint16_t)(((p->tile & 1) ? 0x1000 : 0) + (p->tile & 0xFE) * 16 + (row >= 8 ? 16 : 0))
                                : (uint16_t)(cyc_render_line_sprite_table(y) + p->tile * 16);
        uint8_t b0, b1;
        line_banks(l, y, &b0, &b1);
        uint8_t lo = chr_byte(b0, b1, (uint16_t)(pattern + (row & 7)));
        uint8_t hi = chr_byte(b0, b1, (uint16_t)(pattern + (row & 7) + 8));
        for (int c = 0; c < 8; c++) {
            int x = ox + p->x + c;
            if (x < 0 || x >= width) continue;
            bool in_native = x >= x0 && x < x0 + 256;
            if (in_native && !native_hidden) continue;   /* the PPU drew it */
            int bit = (p->attr & 0x40) ? c : 7 - c;
            int v = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1);
            if (!v) continue;
            uint8_t behind = in_native ? cyc_frame_bg_opaque()[y * 256 + x - x0] : coverage[y * width + x];
            if ((p->attr & 0x20) && behind) continue;
            out[y * width + x] = cyc_render_color(16 + (p->attr & 3) * 4 + v);
        }
    }
}

/* Margins of a status-bar line: the nametable tiles at the native picture's
 * own left and right edges on that line, repeated outward. */
static void hud_line(uint32_t *out, int width, const Level *l, int y, int hx0)
{
    int sy = cyc_render_line_scroll_y(y < 193 ? 193 : y), sx = cyc_render_line_scroll_x(y < 193 ? 193 : y);
    int nty = sy % 240, ntbase = 0x2000;
    uint16_t table = cyc_render_line_bg_table(y);
    for (int side = 0; side < 2; side++) {
        int ex = (sx + (side ? 255 : 0)) & 511;
        uint16_t nt = (uint16_t)(ntbase + (ex >= 256 ? 0x400 : 0));
        int cx = (ex & 255) >> 3, ry = nty >> 3;
        int tile = cyc_render_nametable((uint16_t)(nt + ry * 32 + cx));
        int attr = cyc_render_nametable((uint16_t)(nt + 0x3C0 + (ry >> 2) * 8 + (cx >> 2)));
        int pal = (attr >> (((ry >> 1) & 1) * 4 + ((cx >> 1) & 1) * 2)) & 3;
        int fx = ex & 7;
        int from = side ? hx0 + 256 : 0, to = side ? width : hx0;
        for (int x = from; x < to; x++) {
            int px = side ? (fx + (x - hx0 - 256) % 8) % 8 : (fx + 8 - ((hx0 - x) % 8)) % 8;
            int v = tile_pixel(l, y, table, tile, nty & 7, 7 - px);
            out[y * width + x] = cyc_render_color(v ? pal * 4 + v : 0);
        }
    }
}

static int anchored_origin(int width, int cam, int lw)
{
    int x0 = (width - 256) / 2;
    if (lw <= width) return cam + (width - lw) / 2;
    if (x0 > cam) x0 = cam;
    if (x0 < cam + width - lw) x0 = cam + width - lw;
    return x0;
}

static int render(uint32_t *out, int width, int height, int x0, const uint32_t *native, void *user)
{
    (void)user; (void)height;
    last_scene = enabled ? scene() : SCENE_NONE;
    if (!enabled || last_scene == SCENE_NONE || !(cyc_render_line_mask(80) & 8)) return 0;
    Level l;
    if (!level_now(&l)) return 0;
    int cam = unwrap(cyc_render_line_scroll_x(80), game_camera(), 512);
    int px0 = x0;
    if (last_scene == SCENE_SCROLL && anchored) px0 = anchored_origin(width, cam, l.width);
    last_origin = px0;
    cyc_render_set_native_origin(px0);
    memset(coverage, 0, (size_t)width * 240);
    const uint8_t *opaque = cyc_frame_bg_opaque();
    uint32_t backdrop = cyc_render_color(0);
    for (int y = 0; y < 240; y++) {
        uint32_t *row = out + y * width;
        if (y >= PF_LINES) {
            memcpy(row + x0, native + y * 256, 256 * sizeof(uint32_t));
            hud_line(out, width, &l, y, x0);
            continue;
        }
        memcpy(row + px0, native + y * 256, 256 * sizeof(uint32_t));
        for (int x = 0; x < 256; x++) coverage[y * width + px0 + x] = opaque[y * 256 + x];
        uint16_t table = cyc_render_line_bg_table(y);
        bool bg_on = (cyc_render_line_mask(y) & 8) != 0;
        int last = -1, tile = 0, pal = 0;
        bool valid = false;
        for (int x = 0; x < width; x++) {
            if (x == px0) { x += 255; continue; }
            row[x] = backdrop;
            if (last_scene != SCENE_SCROLL || !bg_on) continue;
            int wx = cam + x - px0;
            if ((wx >> 3) != last) {
                last = wx >> 3;
                valid = decode(&l, wx, y, &tile, &pal);
            }
            if (!valid) continue;
            int v = tile_pixel(&l, y, table, tile, y & 7, 7 - (wx & 7));
            if (v) { row[x] = cyc_render_color(pal * 4 + v); coverage[y * width + x] = 1; }
        }
    }
    if (cyc_render_line_mask(80) & 16)
        for (int i = ws.display_count - 1; i >= 0; i--) {
            const Piece *p = &ws.display[i];
            draw_piece(out, width, &l, px0, p, p->x < 0 || p->x > 255, px0);
        }
    return 1;
}

/* Decoder against the PPU's own background opacity in the native picture. */
static void verify_map(void)
{
    map_samples = map_errors = 0;
    /* Guardian rooms add speech windows and other authored overlays to their
     * nametable. They present native pixels with backdrop margins, so those
     * overlays are not terrain-decoder failures. */
    if (!enabled || scene() == SCENE_NONE || R(0x4F) >= 8) return;
    Level l;
    if (!level_now(&l)) return;
    int cam = unwrap(cyc_render_line_scroll_x(80), game_camera(), 512);
    const uint8_t *opaque = cyc_frame_bg_opaque();
    for (int y = 0; y < PF_LINES; y++) {
        if (unwrap(cyc_render_line_scroll_x(y), cam, 512) != cam) continue;   /* not a playfield line */
        for (int x = 0; x < 256; x++) {
            int tile, pal, wx = cam + x;
            if (!decode(&l, wx, y, &tile, &pal)) continue;
            int v = tile_pixel(&l, y, cyc_render_line_bg_table(y), tile, y & 7, 7 - (wx & 7));
            int mask = cyc_render_line_mask(y);
            int expect = v && (mask & 8) && (x >= 8 || (mask & 2));
            map_samples++;
            map_errors += expect != opaque[y * 256 + x];
        }
    }
}

/* ---- lifecycle ---- */
static int save_state(uint8_t *buf, int cap);
static int load_state(const uint8_t *buf, int len);
static int validate_state(const uint8_t *buf, int len);
static void enable(int on)
{
    static int registered;
    /* The presentation record joins save states only once the mod has been
     * on: a run that never enables it saves exactly the stock state. */
    if (on && !registered) {
        registered = nes_mod_register_savestate_hook(WS_PLUGIN ".presentation", save_state, load_state) &&
                     nes_mod_register_savestate_validator(WS_PLUGIN ".presentation", validate_state);
        if (!registered) fprintf(stderr, "[widescreen] cannot register the presentation state\n");
    }
    enabled = on;
    for (int i = 0; i < H_COUNT; i++) {
        bool policy = i == H_SPAWN || i == H_CULL16 || i == H_CULL64;
        nes_mod_set_function_hook_enabled(hook_ids[i], on && (!policy || viewport));
    }
    cyc_video_set_mode(on ? aspect : NES_VIDEO_STOCK);
    cyc_render_set_compositor(on ? render : NULL, NULL);
    memset(&ws, 0, sizeof ws);
}
static void reset_mod(void) { viewport = 1; anchored = 1; enable(0); }
static void activate(void)
{
    char a[32] = "fit", e[32] = "viewport", c[32] = "anchored";
    nes_mod_option_value(WS_PACKAGE, "widescreen", "aspect", a, sizeof a);
    nes_mod_option_value(WS_PACKAGE, "widescreen", "enemy_activation", e, sizeof e);
    nes_mod_option_value(WS_PACKAGE, "widescreen", "camera", c, sizeof c);
    if (!nes_video_geometry_parse(a, &aspect) || aspect == NES_VIDEO_STOCK) aspect = NES_VIDEO_FIT;
    viewport = !strcmp(e, "viewport");
    anchored = !strcmp(c, "anchored");
    enable(1);
}

const CycHostOption mp_ws_options[] = {
    {"--widescreen", true, "fit|16:9|21:9|32:9|off: adaptive widescreen (experimental)"},
    {"--widescreen-enemies", true, "classic|viewport: original spawning, or activation across the wide view"},
    {"--widescreen-camera", true, "centered|anchored: keep the screen centered, or stop at area edges"},
    {"--widescreen-report", true, "FILE: periodic widescreen diagnostics (JSON lines)"},
};
const size_t mp_ws_option_count = sizeof mp_ws_options / sizeof mp_ws_options[0];

bool mp_ws_option(const char *name, const char *value)
{
    if (!strcmp(name, "--widescreen")) {
        if (!strcmp(value, "off")) { enable(0); return true; }
        int m;
        if (!nes_video_geometry_parse(value, &m) || m == NES_VIDEO_STOCK) return false;
        aspect = m;
        enable(1);
        return true;
    }
    if (!strcmp(name, "--widescreen-enemies")) {
        if (strcmp(value, "viewport") && strcmp(value, "classic")) return false;
        viewport = !strcmp(value, "viewport");
        if (enabled) enable(1);
        return true;
    }
    if (!strcmp(name, "--widescreen-camera")) {
        if (strcmp(value, "centered") && strcmp(value, "anchored")) return false;
        anchored = !strcmp(value, "anchored");
        return true;
    }
    if (!strcmp(name, "--widescreen-report")) {
        report = fopen(value, "w");
        return report != NULL;
    }
    return false;
}

void mp_ws_power_on(void)
{
    memset(&ws, 0, sizeof ws);
    report_frame = 0;
}

static void debug_fields(char *out, size_t cap)
{
    CycModStats ms;
    cyc_mod_stats(&ms);
    snprintf(out, cap,
             "\"enabled\":%s,\"viewport\":%s,\"anchored\":%s,\"width\":%d,\"scene\":%d,\"camera\":%d,\"origin\":%d,"
             "\"area\":%d,\"page_offset\":%d,\"last_page\":%d,\"pieces\":%d,\"captures\":%llu,\"spawns\":%llu,"
             "\"retains\":%llu,\"culls\":%llu,\"suppressed\":%llu,\"overflow\":%llu,\"failures\":%llu,"
             "\"mod_failures\":%llu,\"terrain_samples\":%d,\"terrain_errors\":%d",
             enabled ? "true" : "false", viewport ? "true" : "false", anchored ? "true" : "false", cyc_video_width(),
             scene(), scene() ? unwrap(cyc_render_line_scroll_x(80), game_camera(), 512) : -1, last_origin, R(0x4F), R(0x51), R(0x32E), ws.display_count,
             (unsigned long long)captures, (unsigned long long)spawns, (unsigned long long)retains,
             (unsigned long long)culls, (unsigned long long)suppressed, (unsigned long long)overflow,
             (unsigned long long)failures, (unsigned long long)ms.failures, map_samples, map_errors);
}

void mp_ws_frame_end(void)
{
    uint64_t frame = ++report_frame;
    if (enabled) {
        Level l;
        if (scene() != SCENE_NONE) level_now(&l);   /* fill ROM caches outside the compositor */
        viewport_forget();
    }
    if (!report || frame % 60) return;
    verify_map();
    char fields[1024];
    debug_fields(fields, sizeof fields);
    fprintf(report, "{\"frame\":%llu,%s}\n", (unsigned long long)frame, fields);
    fflush(report);
}

/* ---- save states ---- */
static int validate_state(const uint8_t *buf, int len)
{
    if (!buf) return len == 0;
    if (len != (int)sizeof ws) return 0;
    WsState v;
    memcpy(&v, buf, sizeof v);
    if (v.magic != WS_MAGIC || v.build_count > MAX_PIECES || v.display_count > MAX_PIECES || v.building > 1) return 0;
    for (int i = 0; i < 256; i++) if (v.ledger[i] > 1) return 0;
    return 1;
}
static int save_state(uint8_t *buf, int cap)
{
    if (!enabled) return 0;
    if (cap < (int)sizeof ws) return -1;
    ws.magic = WS_MAGIC;
    memcpy(buf, &ws, sizeof ws);
    return (int)sizeof ws;
}
static int load_state(const uint8_t *buf, int len)
{
    if (!validate_state(buf, len)) return 0;
    memset(&ws, 0, sizeof ws);
    if (buf && len) memcpy(&ws, buf, sizeof ws);
    return 1;
}

/* ---- TCP ---- */
static void tcp_state(int id, const char *line)
{
    bool verify = false;
    cyc_tcp_bool(line, "verify", &verify);
    if (verify) verify_map();
    char fields[1024];
    debug_fields(fields, sizeof fields);
    cyc_tcp_ok(id, fields);
}
static void tcp_poke(int id, const char *line)
{
    long addr, val;
    if (!cyc_tcp_long(line, "addr", &addr) || !cyc_tcp_long(line, "value", &val) || addr < 0 || addr > 0x7FF || val < 0 ||
        val > 255 || !W(addr, val)) {
        cyc_tcp_err(id, "ws_poke: CPU RAM addr and byte value");
        return;
    }
    cyc_render_frame_done();
    cyc_tcp_ok(id, NULL);
}
static void tcp_step(int id, const char *line)
{
    long frames = 1, pad = 0;
    cyc_tcp_long(line, "frames", &frames);
    cyc_tcp_long(line, "pad", &pad);
    if (frames < 1 || frames > 600 || pad < 0 || pad > 255) { cyc_tcp_err(id, "ws_step: frames 1..600, pad 0..255"); return; }
    cyc_set_controller(0, (uint8_t)pad);
    for (long i = 0; i < frames; i++) { cyc_session_frame_begin(); cyc_run_frame(); cyc_session_frame_end(); }
    cyc_set_controller(0, 0);
    cyc_tcp_ok(id, NULL);
}
static void tcp_packets(int id, const char *line)
{
    (void)line;
    static char out[16384];
    size_t pos = (size_t)snprintf(out, sizeof out, "\"origin\":%d,\"pieces\":[", last_origin);
    for (int i = 0; i < ws.display_count && pos < sizeof out - 64; i++) {
        const Piece *p = &ws.display[i];
        pos += (size_t)snprintf(out + pos, sizeof out - pos, "%s[%d,%u,%u,%u]", i ? "," : "", p->x, p->y, p->tile, p->attr);
    }
    snprintf(out + pos, sizeof out - pos, "]");
    cyc_tcp_ok(id, out);
}
void mp_ws_tcp_setup(void)
{
    cyc_tcp_register("ws_state", "widescreen diagnostics; verify:true checks the terrain decoder", tcp_state);
    cyc_tcp_register("ws_poke", "test fixture: write a CPU RAM byte", tcp_poke);
    cyc_tcp_register("ws_step", "test fixture: advance frames (frames, pad)", tcp_step);
    cyc_tcp_register("ws_packets", "signed sprite pieces shown in the margins", tcp_packets);
}

NES_MOD_CONSTRUCTOR(mp_register_widescreen)
{
    nes_mod_register_reset_callback(reset_mod);
    nes_mod_register_activation_plugin(WS_PLUGIN, activate);
    for (int i = 0; i < H_COUNT; i++) nes_mod_register_function_entry_plugin(hook_ids[i], hook_addrs[i], hook);
}
