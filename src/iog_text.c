/* Illusion of Gaia text pipeline (see iog_text.h). */

#include "iog_text.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- text engine command set (identical in every release) ------------- */

enum {
    CMD_END = 0xC0, CMD_ADR = 0xC5, CMD_RET = 0xCA, CMD_N = 0xCB,
    CMD_PRT = 0xCD, CMD_FIN = 0xCF, CMD_JMP = 0xD1, CMD_SFX = 0xD2, CMD_LU1 = 0xD6,
    CMD_LU2 = 0xD7, CMD_ESC = 0xD8, CMD_LAST = 0xDA,
};
/* Argument sizes in bytes per command $C0-$DA; ESC is delimited by $00. */
static const uint8_t kArgs[CMD_LAST - 0xC0 + 1][2] = {
    [0x00] = {0, 0}, [0x01] = {1, 1}, [0x02] = {1, 0}, [0x03] = {1, 0},
    [0x04] = {0, 0}, [0x05] = {2, 2}, [0x06] = {2, 2}, [0x07] = {1, 1},
    [0x08] = {0, 0}, [0x09] = {1, 0}, [0x0A] = {0, 0}, [0x0B] = {0, 0},
    [0x0C] = {1, 0}, [0x0D] = {3, 0}, [0x0E] = {0, 0}, [0x0F] = {0, 0},
    [0x10] = {0, 0}, [0x11] = {2, 0}, [0x12] = {1, 0}, [0x13] = {0, 0},
    [0x14] = {1, 2}, [0x15] = {1, 0}, [0x16] = {1, 0}, [0x17] = {1, 0},
    [0x18] = {0, 0}, [0x19] = {1, 0}, [0x1A] = {1, 0},
};
/* Commands whose presence and order make up a string's "skeleton". */
static int IsSkeleton(uint8_t c)
{
    switch (c) {
    case 0xC1: case 0xC7: case 0xC2: case 0xC3: case 0xD2: case 0xC5: case 0xC6:
    case 0xD5: case 0xD4: case 0xDA: case 0xCC: case 0xD9: case 0xC9: case 0xD3:
    case 0xC8:
        return 1;
    }
    return 0;
}
static int IsHalt(uint8_t c) { return c == CMD_END || c == CMD_RET || c == CMD_JMP; }
static int IsRef(uint8_t c) { return c == CMD_ADR || c == CMD_PRT || c == CMD_JMP; }

/* ---- tokens ------------------------------------------------------------ */

enum { T_GLYPH, T_CMD, T_MARK };

typedef struct {
    uint8_t type, code;
    uint32_t a[3];             /* raw argument values */
    int ref;                   /* resolved label/table index, -1: numeric */
    uint8_t ref_m;             /* reference is to the target's [::] marker */
    uint8_t blen;
    uint8_t bin[24];           /* ESC payload */
    uint32_t src;              /* source byte offset of the top-level token */
} Tok;

typedef struct {
    Tok *t;
    int n, cap;
} Toks;

static void Push(Toks *v, const Tok *t)
{
    if (v->n == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 64;
        v->t = realloc(v->t, (size_t)v->cap * sizeof(Tok));
    }
    v->t[v->n++] = *t;
}

typedef struct {
    const uint8_t *rom;
    size_t size;
    uint32_t engine;
    uint32_t dict[2];          /* [LU1], [LU2] tables (ROM offsets) */
} Rom;

static uint32_t Rd16(const Rom *r, uint32_t off)
{
    return off + 1 < r->size ? (uint32_t)(r->rom[off] | r->rom[off + 1] << 8) : 0;
}

static const uint8_t kEngineSig[] = {
    0x08, 0x0b, 0xda, 0xa9, 0x00, 0x00, 0x5b, 0xae, 0x98, 0x09, 0xe2, 0x20, 0xb9, 0x00, 0x00, 0xc9,
};

static int RomInit(Rom *r, const uint8_t *rom, size_t size)
{
    r->rom = rom;
    r->size = size;
    r->engine = 0;
    for (size_t i = 0; i + sizeof(kEngineSig) <= size; i++)
        if (!memcmp(rom + i, kEngineSig, sizeof(kEngineSig))) {
            r->engine = (uint32_t)i;
            break;
        }
    if (!r->engine)
        return 0;
    /* The command table is $6E past the engine entry; entries $16/$17 are
     * the dictionary handlers: SEP #$20 / LDA #bank / PHA / PLB / REP #$20 /
     * LDA table,Y. */
    for (int k = 0; k < 2; k++) {
        uint32_t h = (r->engine & 0xFF0000) | Rd16(r, r->engine + 0x6E + 2 * (0x16 + k));
        r->dict[k] = 0;
        for (uint32_t i = h; i < h + 40 && i + 11 < size; i++) {
            const uint8_t *p = rom + i;
            if (p[0] == 0xE2 && p[1] == 0x20 && p[2] == 0xA9 && p[4] == 0x48 && p[5] == 0xAB &&
                p[6] == 0xC2 && p[7] == 0x20 && p[8] == 0xB9) {
                r->dict[k] = ((uint32_t)(p[3] & 0x3F) << 16) | p[9] | p[10] << 8;
                break;
            }
        }
        if (!r->dict[k])
            return 0;
    }
    return 1;
}

/* Decode one string at `off` into `out`. Dictionary references are
 * expanded; a word's own [RET] is dropped. Returns 0 on data that is not
 * text (bad command, glyph code of a font bottom half, runaway). */
static int Decode(const Rom *r, uint32_t off, Toks *out, int depth, uint32_t src_base)
{
    uint32_t i = off;
    while (i < r->size && i - off < 4096) {
        Tok t = {0};
        t.ref = -1;
        t.src = depth ? src_base : i;
        uint8_t b = r->rom[i++];
        if (b < 0xC0) {
            if (b & 0x10)
                return 0;               /* bottom-half tile: not a glyph */
            t.type = T_GLYPH;
            t.code = b;
            Push(out, &t);
            continue;
        }
        if (b > CMD_LAST)
            return 0;
        t.type = T_CMD;
        t.code = b;
        if (b == CMD_ESC) {
            while (i < r->size && r->rom[i] != 0 && t.blen < sizeof(t.bin))
                t.bin[t.blen++] = r->rom[i++];
            if (i >= r->size || r->rom[i] != 0)
                return 0;
            i++;
            Push(out, &t);
            continue;
        }
        for (int k = 0; k < 2; k++) {
            int n = kArgs[b - 0xC0][k];
            uint32_t v = 0;
            for (int j = 0; j < n; j++)
                v |= (uint32_t)r->rom[i + j] << (8 * j);
            i += (uint32_t)n;
            t.a[k] = v;
        }
        if ((b == CMD_LU1 || b == CMD_LU2) && depth < 4) {
            uint32_t table = r->dict[b - CMD_LU1];
            uint32_t word = (table & 0xFF0000) | Rd16(r, table + 2 * t.a[0]);
            int before = out->n;
            if (!Decode(r, word, out, depth + 1, t.src))
                return 0;
            if (out->n > before && out->t[out->n - 1].type == T_CMD &&
                out->t[out->n - 1].code == CMD_RET)
                out->n--;
            continue;
        }
        Push(out, &t);
        if (IsHalt(b))
            return 1;
    }
    return 0;
}

/* Bytes the string at `off` occupies in this ROM, up to and including the
 * command that ends it (dictionary words are references, not inline).
 * 0 when it does not decode. A redirect written over a string must fit in
 * this: what follows a string can be code (e.g. $08:F37B "[CLD]", two bytes
 * right before the Freedan->Will animation, whose COP 8E a 5-byte redirect
 * overwrote: Will came back from Freedan with scrambled sprites). */
static uint32_t StringSpan(const Rom *r, uint32_t off)
{
    uint32_t i = off;
    while (i < r->size && i - off < 4096) {
        const uint8_t b = r->rom[i++];
        if (b < 0xC0) {
            if (b & 0x10)
                return 0;
            continue;
        }
        if (b > CMD_LAST)
            return 0;
        if (b == CMD_ESC) {
            while (i < r->size && r->rom[i] != 0)
                i++;
            if (i >= r->size)
                return 0;
            i++;
            continue;
        }
        i += (uint32_t)(kArgs[b - 0xC0][0] + kArgs[b - 0xC0][1]);
        if (IsHalt(b))
            return i - off;
    }
    return 0;
}

/* ---- structure (i18n/structure.txt) ------------------------------------ */

typedef struct {
    char name[24];
    int unk16;
    uint32_t off;
    uint32_t marker;           /* byte offset in the USA encoding, 0: none */
    int has_marker;
    int scene;                 /* scene title (see SceneTitle) */
} Label;

typedef struct {
    char name[32];
    uint32_t off;
    int n;
    int entry[256];
    uint8_t entry_m[256];
} Table;

typedef struct {
    Label *l;
    int nl;
    Table *t;
    int nt;
    uint32_t font_ptr[8];      /* USA offsets of scene_meta font pointers ([0]: BG3) */
    int nfont;
    uint32_t map_table, map_start, map_end;   /* overworld names (sprite text) */
    uint32_t pro_str[16], pro_site[16];       /* prologue strings, LDA #imm operand */
    int npro;
    uint32_t free_start, free_end;            /* $FF padding in the prologue's bank */
    uint32_t scene_table;                     /* scene_actors: word pointer per map */
    int scene_n;
    uint32_t *ascii;           /* menu/item strings (ASCII engine) */
    int nascii;
    uint32_t ptab[32];         /* tables reached by ASCII [PTR] */
    int ptab_n[32];
    int nptab;
} Structure;

static int FindLabel(const Structure *s, const char *name)
{
    for (int i = 0; i < s->nl; i++)
        if (!strcmp(s->l[i].name, name))
            return i;
    return -1;
}

static int LoadStructure(Structure *s, const char *path)
{
    FILE *f = fopen(path, "r");
    if (!f)
        return 0;
    char line[8192];
    memset(s, 0, sizeof(*s));
    s->l = calloc(4096, sizeof(Label));
    s->t = calloc(32, sizeof(Table));
    /* Tables name labels, so resolve them after every label is known. */
    char *tables[32];
    int ntab = 0;
    while (fgets(line, sizeof(line), f)) {
        if (line[0] == 'S' && s->nl < 4096) {
            Label *l = &s->l[s->nl];
            char kind[16];
            unsigned off, mk;
            int used = 0;
            if (sscanf(line, "S %23s %15s %x%n", l->name, kind, &off, &used) < 3)
                continue;
            l->off = off;
            l->unk16 = !strcmp(kind, "unk16");
            if (sscanf(line + used, " %x", &mk) == 1) {
                l->marker = mk;
                l->has_marker = 1;
            }
            s->nl++;
        } else if (line[0] == 'A' && s->nascii < 1024) {
            char nm[64];
            unsigned off;
            if (!s->ascii)
                s->ascii = calloc(1024, sizeof(uint32_t));
            if (sscanf(line, "A %63s %x", nm, &off) == 2)
                s->ascii[s->nascii++] = off;
        } else if (line[0] == 'P' && s->nptab < 32) {
            char nm[64];
            unsigned off;
            int n;
            if (sscanf(line, "P %63s %x %d", nm, &off, &n) == 3) {
                s->ptab[s->nptab] = off;
                s->ptab_n[s->nptab++] = n;
            }
        } else if (line[0] == 'F') {
            unsigned off;
            if (sscanf(line, "F %x", &off) == 1 && s->nfont < 8)
                s->font_ptr[s->nfont++] = off;
        } else if (line[0] == 'N') {
            unsigned a, b, c;
            if (sscanf(line, "N %x %x %x", &a, &b, &c) == 3)
                s->map_table = a, s->map_start = b, s->map_end = c;
        } else if (line[0] == 'Q' && s->npro < 16) {
            unsigned a, b;
            if (sscanf(line, "Q %x %x", &a, &b) == 2)
                s->pro_str[s->npro] = a, s->pro_site[s->npro++] = b;
        } else if (line[0] == 'E') {
            unsigned a;
            int n;
            if (sscanf(line, "E %x %d", &a, &n) == 2)
                s->scene_table = a, s->scene_n = n;
        } else if (line[0] == 'Z') {
            unsigned a, b;
            if (sscanf(line, "Z %x %x", &a, &b) == 2)
                s->free_start = a, s->free_end = b;
        } else if (line[0] == 'T' && ntab < 32) {
            tables[ntab++] = strdup(line);
        }
    }
    fclose(f);
    for (int k = 0; k < ntab; k++) {
        Table *t = &s->t[s->nt];
        unsigned off;
        int used = 0;
        if (sscanf(tables[k], "T %31s %x%n", t->name, &off, &used) >= 2) {
            t->off = off;
            char *p = tables[k] + used, *tok;
            while ((tok = strtok(p, " \n")) && t->n < 256) {
                p = NULL;
                char *plus = strstr(tok, "+M");
                t->entry_m[t->n] = plus != NULL;
                if (plus)
                    *plus = 0;
                t->entry[t->n++] = FindLabel(s, tok);
            }
            s->nt++;
        }
        free(tables[k]);
    }
    return s->nl > 0;
}

/* ---- USA references ----------------------------------------------------- */

static int LabelAt(const Structure *s, uint32_t off, uint8_t *m)
{
    for (int i = 0; i < s->nl; i++) {
        if (s->l[i].off == off) {
            *m = 0;
            return i;
        }
        if (s->l[i].has_marker && s->l[i].off + s->l[i].marker == off) {
            *m = 1;
            return i;
        }
    }
    return -1;
}

/* Turn a decoded USA string's numeric references into label/table refs and
 * put its [::] marker back. Returns 0 if a bank-relative reference names
 * something the structure does not know (the string then stays in ROM). */
static int ResolveUsa(const Structure *s, int li, Toks *v)
{
    uint32_t bank = s->l[li].off & 0xFF0000;
    int ok = 1;
    for (int i = 0; i < v->n; i++) {
        Tok *t = &v->t[i];
        if (t->type != T_CMD || !IsRef(t->code))
            continue;
        if (t->code == CMD_ADR) {
            t->ref = -1;
            for (int k = 0; k < s->nt; k++)
                if (s->t[k].off == (bank | t->a[0]))
                    t->ref = k;
            ok &= t->ref >= 0;
        } else if (t->code == CMD_JMP) {
            t->ref = LabelAt(s, bank | t->a[0], &t->ref_m);
            ok &= t->ref >= 0;
        } else {            /* PRT: 24-bit, may stay a ROM address */
            t->ref = LabelAt(s, ((t->a[0] & 0x3F0000) | (t->a[0] & 0xFFFF)), &t->ref_m);
        }
    }
    if (s->l[li].has_marker) {
        Tok mk = {0};
        mk.type = T_MARK;
        mk.ref = -1;
        int at = v->n;
        for (int i = 0; i < v->n; i++)
            if (v->t[i].src >= s->l[li].off + s->l[li].marker) {
                at = i;
                break;
            }
        Push(v, &mk);
        memmove(&v->t[at + 1], &v->t[at], (size_t)(v->n - 1 - at) * sizeof(Tok));
        v->t[at] = mk;
    }
    return ok;
}

/* ---- pairing ------------------------------------------------------------- */

typedef struct {
    uint32_t off, target;
    uint8_t op;
    int li;                    /* USA: label; EU: index into eu strings */
} Site;

/* Text engine call sites:
 *   COP BF / COP 6B <ptr16>       string in the script's bank
 *   COP 19 <music> <addr24>       music + string
 *   LDY #<ptr16> / JSL <routine>  string in a bank the routine selects; the
 *                                 banks to try come from the USA pairs */
static int Sites(const uint8_t *rom, size_t size, Site *out, int max, const uint8_t *ldy_banks,
                 int nldy)
{
    int n = 0;
    for (size_t i = 16; i + 16 < size && n < max; i++) {
        if (rom[i] == 0x02 && (rom[i + 1] == 0xBF || rom[i + 1] == 0x6B)) {
            out[n++] = (Site){(uint32_t)i, ((uint32_t)i & 0xFF0000) | rom[i + 2] | rom[i + 3] << 8,
                              rom[i + 1], -1};
        } else if (rom[i] == 0x02 && rom[i + 1] == 0x19) {
            uint32_t a = rom[i + 3] | rom[i + 4] << 8 | (uint32_t)rom[i + 5] << 16;
            out[n++] = (Site){(uint32_t)i, ((a >> 16) & 0x3F) << 16 | (a & 0xFFFF), 0x19, -1};
        } else if (rom[i] == 0xA0 && rom[i + 3] == 0x22) {
            for (int b = 0; b < nldy && n < max; b++)
                out[n++] = (Site){(uint32_t)i, (uint32_t)ldy_banks[b] << 16 | rom[i + 1] | rom[i + 2] << 8,
                                  0xA0, -1};
        }
    }
    return n;
}

static int Skeleton(const Toks *v, uint8_t *out, int max)
{
    int n = 0;
    for (int i = 0; i < v->n && n < max; i++)
        if (v->t[i].type == T_CMD && IsSkeleton(v->t[i].code))
            out[n++] = v->t[i].code;
    return n;
}

typedef struct {
    Toks toks;
    uint8_t skel[64];
    int nskel;
} Text;

static int Score(const Rom *us, const Site *a, const Text *at, const Rom *eu, const Site *b,
                 const Text *bt)
{
    if (a->op != b->op)
        return -1;
    int s = 0;
    /* Script bytes after the operand (for LDY, after the JSL too). */
    int post = a->op == 0x19 ? 6 : a->op == 0xA0 ? 7 : 4;
    for (int k = 1; k <= 8; k++)
        s += us->rom[a->off - k] == eu->rom[b->off - k];
    for (int k = post; k < post + 6; k++)
        s += us->rom[a->off + k] == eu->rom[b->off + k];
    if (at->nskel == bt->nskel && !memcmp(at->skel, bt->skel, (size_t)at->nskel))
        s += 6;
    return s >= 10 ? s : -1;
}

/* ---- encoding and placement --------------------------------------------- */

typedef struct {
    int li;
    Toks toks;
    int bank_index, pos, len;
    int placed, relocatable;
    uint8_t tail[4];
} Item;

static uint32_t HiromAddr(uint32_t off)
{
    return (off & 0x8000) ? (0x800000 | off) : (0xC00000 | off);
}

enum { kVBankFirst = 0xA0, kVBase = 0x8000 };

typedef struct {
    Item *items;
    int nitems;
    int *item_of_label;
    int *table_bank, *table_pos;
    const Structure *s;
} Layout;

static int MarkerPos(const Item *it)
{
    int pos = 0;
    for (int i = 0; i < it->toks.n; i++) {
        const Tok *t = &it->toks.t[i];
        if (t->type == T_MARK)
            return pos;
        pos += t->type == T_GLYPH ? 1 : 1 + kArgs[t->code - 0xC0][0] + kArgs[t->code - 0xC0][1] +
               (t->code == CMD_ESC ? t->blen + 1 : 0);
    }
    return 0;
}

/* Encode one item. With lay == NULL references encode as 0 (sizing).
 * Returns the length, or -1 when a reference cannot be expressed. */
static int Encode(const Layout *lay, const Item *it, uint8_t *out)
{
    int n = 0, last_halt = 0;
    for (int i = 0; i < it->toks.n; i++) {
        const Tok *t = &it->toks.t[i];
        last_halt = 0;
        if (t->type == T_MARK)
            continue;
        if (t->type == T_GLYPH) {
            if (out)
                out[n] = t->code;
            n++;
            continue;
        }
        if (out)
            out[n] = t->code;
        n++;
        if (t->code == CMD_ESC) {
            if (out)
                memcpy(out + n, t->bin, t->blen), out[n + t->blen] = 0;
            n += t->blen + 1;
            continue;
        }
        uint32_t a0 = t->a[0];
        if (lay && IsRef(t->code) && t->ref >= 0) {
            if (t->code == CMD_ADR) {
                if (lay->table_bank[t->ref] != it->bank_index)
                    return -1;
                /* Every entry must live in this virtual bank too. */
                const Table *tb = &lay->s->t[t->ref];
                for (int e = 0; e < tb->n; e++) {
                    int ei = tb->entry[e] >= 0 ? lay->item_of_label[tb->entry[e]] : -1;
                    if (ei < 0 || !lay->items[ei].placed ||
                        lay->items[ei].bank_index != it->bank_index)
                        return -1;
                }
                a0 = kVBase + (uint32_t)lay->table_pos[t->ref];
            } else {
                int ti = lay->item_of_label[t->ref];
                const Item *tg = ti >= 0 ? &lay->items[ti] : NULL;
                if (tg && tg->placed) {
                    uint32_t p = kVBase + (uint32_t)tg->pos + (t->ref_m ? (uint32_t)MarkerPos(tg) : 0);
                    if (t->code == CMD_JMP) {
                        if (tg->bank_index != it->bank_index)
                            return -1;
                        a0 = p;
                    } else {
                        a0 = ((uint32_t)(kVBankFirst + tg->bank_index) << 16) | p;
                    }
                } else if (t->code == CMD_PRT) {
                    const Label *l = &lay->s->l[t->ref];
                    a0 = HiromAddr(l->off + (t->ref_m ? l->marker : 0));
                } else {
                    return -1;
                }
            }
        } else if (lay && IsRef(t->code) && t->code != CMD_PRT) {
            return -1;          /* bank-relative reference nobody resolved */
        }
        uint32_t args[2] = {a0, t->a[1]};
        for (int k = 0; k < 2; k++)
            for (int j = 0; j < kArgs[t->code - 0xC0][k]; j++) {
                if (out)
                    out[n] = (uint8_t)(args[k] >> (8 * j));
                n++;
            }
        last_halt = IsHalt(t->code);
    }
    if (!last_halt) {
        if (out)
            out[n] = CMD_RET;
        n++;
    }
    /* unk16 blocks carry a raw 4-byte tail after their [RET]; the sizing
     * pass (lay == NULL) leaves it to the caller. */
    if (lay && lay->s->l[it->li].unk16) {
        if (out)
            memcpy(out + n, it->tail, 4);
        n += 4;
    }
    return n;
}

const char *IogTextRomLanguage(const uint8_t *rom, size_t size)
{
    if (size < 0x10000 || memcmp(rom + 0xFFC0, "ILLUSION OF TIME ", 17))
        return NULL;
    const char *r = (const char *)rom + 0xFFC0 + 17;
    if (!memcmp(r, "SPN", 3)) return "es";
    if (!memcmp(r, "FRA", 3)) return "fr";
    if (!memcmp(r, "GRM", 3)) return "de";
    if (!memcmp(r, "ITA", 3)) return "it";
    return NULL;
}

static const char *LanguageName(const char *code)
{
    if (!strcmp(code, "es")) return "Español";
    if (!strcmp(code, "fr")) return "Français";
    if (!strcmp(code, "de")) return "Deutsch";
    if (!strcmp(code, "it")) return "Italiano";
    return code;
}

/* Append a patch of `len` bytes at USA offset `off`. */
static void AddPatch(IogPack *pack, uint32_t off, const uint8_t *bytes, uint32_t len)
{
    if (pack->npatches == pack->cap_patches) {
        pack->cap_patches = pack->cap_patches ? pack->cap_patches * 2 : 1024;
        pack->patches = realloc(pack->patches, (size_t)pack->cap_patches * sizeof(IogPatch));
    }
    IogPatch *p = &pack->patches[pack->npatches++];
    p->offset = off;
    p->len = len;
    p->data = malloc(len);
    p->original = calloc(1, len);
    memcpy(p->data, bytes, len);
}

static void AddRedirect(IogPack *pack, uint32_t off, uint8_t cmd, uint32_t addr, uint8_t end)
{
    const uint8_t b[5] = {cmd, (uint8_t)addr, (uint8_t)(addr >> 8), (uint8_t)(addr >> 16), end};
    AddPatch(pack, off, b, 5);
}

/* ---- QuintetLZ (the game's graphics compression) ------------------------ */

/* Decompress at `off` into out (cap bytes). Returns the decompressed size,
 * 0 on malformed data; *consumed gets the compressed size. */
static size_t QuintetExpand(const Rom *r, uint32_t off, uint8_t *out, size_t cap, size_t *consumed)
{
    if (off + 2 > r->size)
        return 0;
    size_t len = r->rom[off] | r->rom[off + 1] << 8;
    if (len > cap)
        return 0;
    uint64_t bit = (uint64_t)(off + 2) * 8;
    uint8_t dict[256];
    memset(dict, 0x20, sizeof(dict));
    unsigned dp = 0xEF;
    size_t n = 0;
#define BITS(k, v) do { v = 0; for (int _b = 0; _b < (k); _b++, bit++) { \
        if ((bit >> 3) >= r->size) return 0; \
        v = v << 1 | (r->rom[bit >> 3] >> (7 - (bit & 7)) & 1); } } while (0)
    while (n < len) {
        unsigned flag, v;
        BITS(1, flag);
        if (flag) {
            BITS(8, v);
            out[n++] = (uint8_t)v;
            dict[dp] = (uint8_t)v;
            dp = (dp + 1) & 0xFF;
        } else {
            unsigned idx, ln;
            BITS(8, idx);
            BITS(4, ln);
            for (ln += 2; ln--; ) {
                uint8_t b = dict[idx];
                idx = (idx + 1) & 0xFF;
                if (n < len)
                    out[n++] = b;
                dict[dp] = b;
                dp = (dp + 1) & 0xFF;
            }
        }
    }
#undef BITS
    *consumed = (size_t)((bit + 7) / 8 - off);
    return n;
}

static uint32_t Ptr24Offset(const Rom *r, uint32_t at)
{
    uint32_t a = r->rom[at] | r->rom[at + 1] << 8 | (uint32_t)r->rom[at + 2] << 16;
    return ((a >> 16) & 0x3F) << 16 | (a & 0xFFFF);
}

/* Find the European counterpart of a USA pointer by the bytes around it. */
static uint32_t FindByContext(const Rom *ru, const Rom *re, uint32_t at, int pre, int width, int post)
{
    if (at < (uint32_t)pre || at + (uint32_t)(width + post) > ru->size)
        return 0;
    const uint8_t *a = ru->rom + at - pre, *b = ru->rom + at + width;
    /* Same place first (most layout data did not move), with a shorter
     * context so an edited neighbouring byte does not hide it. */
    int sp = pre < 4 ? pre : 4;
    if (at + (uint32_t)(width + post) <= re->size &&
        !memcmp(re->rom + at - sp, ru->rom + at - sp, (size_t)sp) &&
        !memcmp(re->rom + at + width, b, (size_t)post))
        return at;
    for (size_t i = 0; i + (size_t)(pre + width + post) < re->size; i++)
        if (!memcmp(re->rom + i, a, (size_t)pre) && !memcmp(re->rom + i + pre + width, b, (size_t)post))
            return (uint32_t)i + (uint32_t)pre;
    return 0;
}

/* Use the European release's fonts: copy their compressed data into a
 * virtual bank and point scene_meta's entries there. The European entries
 * are found by the bytes around the USA pointers. The first one (the BG3
 * text font) is also kept decompressed for swapping VRAM on a live switch. */
static void AddFont(const Structure *st, const Rom *ru, const Rom *re, IogPack *pack)
{
    int vb = -1, fill = kIogVirtualBankSize;
    for (int k = 0; k < st->nfont; k++) {
        uint32_t f = st->font_ptr[k];
        uint32_t at = FindByContext(ru, re, f, 6, 3, 5);
        static uint8_t tmp[0x10000];
        size_t used = 0, usa_used = 0;
        size_t n = at ? QuintetExpand(re, Ptr24Offset(re, at), tmp, sizeof(tmp), &used) : 0;
        if (!n || used > kIogVirtualBankSize) {
            fprintf(stderr, "[i18n] European font %d not found; keeping the USA one\n", k);
            continue;
        }
        if (k == 0) {
            if (n != sizeof(pack->font) ||
                QuintetExpand(ru, Ptr24Offset(ru, f), pack->usa_font, sizeof(pack->usa_font),
                              &usa_used) != sizeof(pack->usa_font))
                continue;
            memcpy(pack->font, tmp, sizeof(pack->font));
            pack->has_font = 1;
        }
        if (fill + (int)used > kIogVirtualBankSize) {
            if (pack->nbanks >= kIogVirtualBanks)
                return;
            vb = pack->nbanks++;
            pack->banks[vb] = calloc(1, kIogVirtualBankSize);
            fill = 0;
        }
        memcpy(pack->banks[vb] + fill, re->rom + Ptr24Offset(re, at), used);
        uint32_t addr = ((uint32_t)(kVBankFirst + vb) << 16) | (kVBase + (uint32_t)fill);
        const uint8_t ptr[3] = {(uint8_t)addr, (uint8_t)(addr >> 8), (uint8_t)(addr >> 16)};
        AddPatch(pack, f, ptr, 3);
        fill += (int)used;
    }
}

/* ---- sprite text (overworld names, prologue) ------------------------------- */

/* ---- scene titles -----------------------------------------------------------
 *
 * scene_actors ($0C:8000) holds a word pointer per map to that map's actor
 * list: 7-byte entries (9 when the seventh byte, an enemy's, is nonzero)
 * up to $FF, then the scene's title as a dialogue string ("Lance's House",
 * "TEST MAP"). The European releases translate them at the same map index.
 * Returns the ROM offset of map m's title, 0 if the list does not parse. */
static uint32_t SceneActorList(const Rom *r, const Structure *st, int m)
{
    uint32_t t = st->scene_table;
    if (!t || m >= st->scene_n || t + 2 * (uint32_t)m + 2 > r->size)
        return 0;
    return (t & 0xFF0000) | Rd16(r, t + 2 * (uint32_t)m);
}

static uint32_t SceneTitle(const Rom *r, const Structure *st, int m)
{
    uint32_t o = SceneActorList(r, st, m);
    if (!o)
        return 0;
    for (int n = 0; n < 256; n++) {
        if (o + 9 > r->size)
            return 0;
        if (r->rom[o] == 0xFF)
            return o + 1;
        o += r->rom[o + 6] ? 9 : 7;
    }
    return 0;
}

/* Title length up to its [RET]; 0 if none nearby. */
static uint32_t SceneTitleLen(const Rom *r, uint32_t off)
{
    for (uint32_t i = off; i < r->size && i < off + 64; i++)
        if (r->rom[i] == CMD_RET)
            return i - off;
    return 0;
}

/* Append a label per distinct USA scene title long enough to take a
 * redirect; scene_map[li] keeps the first map it belongs to. */
static void AddSceneLabels(Structure *st, const Rom *ru, int *scene_map)
{
    for (int m = 0; m < st->scene_n && st->nl < 4096; m++) {
        uint32_t off = SceneTitle(ru, st, m);
        if (!off || SceneTitleLen(ru, off) < 4)
            continue;
        int dup = 0;
        for (int i = 0; i < st->nl && !dup; i++)
            dup = st->l[i].off == off;
        if (dup)
            continue;
        Label *l = &st->l[st->nl];
        memset(l, 0, sizeof(*l));
        snprintf(l->name, sizeof(l->name), "scene_title_%02X", m);
        l->off = off;
        l->scene = 1;
        scene_map[st->nl++] = m;
    }
}

static uint32_t SpriteLen(const Rom *r, uint32_t off)
{
    uint32_t i = off;
    while (i < r->size && r->rom[i] != 0xCA && i - off < 512)
        i++;
    return i < r->size && r->rom[i] == 0xCA ? i - off + 1 : 0;
}

/* The sprite text engine has no redirect command, so its strings move:
 *   - overworld names: the European names are repacked into the USA names'
 *     region and the name table (data) re-pointed, matching entries by map;
 *   - prologue: its pointers are LDA #imm operands in code the interpreter
 *     runs (bank $0B has no compiled functions there), so the European text
 *     goes into the bank's free $FF space and the operands are patched. */
static void AddSprites(const Structure *st, const Rom *ru, const Rom *re, IogPack *pack)
{
    int maps = 0, pro = 0;
    if (st->map_table) {
        /* European table: the lookup routine loads it as LDA #bank / PHA /
         * PLB / LDA table,X; find the routine by the USA code around it. */
        static const uint8_t sig[] = {0x08, 0xDA, 0xA2, 0x00, 0x00, 0xE2, 0x20, 0x8B, 0xA9};
        uint32_t eu_tab = 0;
        for (size_t i = 0; i + 16 < re->size && !eu_tab; i++)
            if (!memcmp(re->rom + i, sig, sizeof(sig)) && re->rom[i + 10] == 0x48 &&
                re->rom[i + 11] == 0xAB && re->rom[i + 12] == 0xBD)
                eu_tab = ((uint32_t)(re->rom[i + 9] & 0x3F) << 16) | re->rom[i + 13] | re->rom[i + 14] << 8;
        uint32_t cap = st->map_end - st->map_start;
        uint8_t *region = eu_tab && cap < 0x4000 ? malloc(cap) : NULL;
        uint32_t fill = 0, placed_eu[64], placed_at[64];
        int nplaced = 0, ok = region != NULL;
        uint32_t ut = st->map_table;
        /* entries: id, ptr16; id 0 ends */
        for (int k = 0; ok && ru->rom[ut + 3 * k] && k < 64; k++) {
            uint8_t id = ru->rom[ut + 3 * k];
            uint32_t eo = 0;
            for (int e = 0; re->rom[eu_tab + 3 * e] && e < 64; e++)
                if (re->rom[eu_tab + 3 * e] == id)
                    eo = (eu_tab & 0xFF0000) | Rd16(re, eu_tab + 3 * e + 1);
            if (!eo)
                continue;
            int j = 0;
            while (j < nplaced && placed_eu[j] != eo)
                j++;
            if (j == nplaced) {
                uint32_t n = SpriteLen(re, eo);
                if (!n || fill + n > cap || nplaced >= 64) {
                    ok = 0;
                    break;
                }
                memcpy(region + fill, re->rom + eo, n);
                placed_eu[nplaced] = eo;
                placed_at[nplaced++] = st->map_start + fill;
                fill += n;
            }
            uint32_t at = placed_at[j];
            const uint8_t ptr[2] = {(uint8_t)at, (uint8_t)(at >> 8)};
            AddPatch(pack, ut + 3 * (uint32_t)k + 1, ptr, 2);
            maps++;
        }
        if (ok && fill)
            AddPatch(pack, st->map_start, region, fill);
        else
            maps = 0;
        free(region);
    }
    if (st->npro && st->free_end > st->free_start) {
        uint32_t cap = st->free_end - st->free_start, fill = 0;
        int clean = 1;
        for (uint32_t i = st->free_start; i < st->free_end; i++)
            clean &= ru->rom[i] == 0xFF;
        uint8_t *space = clean ? malloc(cap) : NULL;
        /* European prologue sites in order: LDA #text / STA $0026,Y. The
         * k-th USA site maps to the k-th one when the script bytes before it
         * differ (longer text moved its position arguments). */
        uint32_t eu_sites[16];
        int neu = 0;
        uint32_t lo = st->pro_site[0] & 0xFF0000, first = st->pro_site[0], last = first;
        for (int k = 1; k < st->npro; k++) {
            if (st->pro_site[k] < first) first = st->pro_site[k];
            if (st->pro_site[k] > last) last = st->pro_site[k];
        }
        for (uint32_t i = first - 0x200; i + 6 < re->size && i < last + 0x200 && neu < 16; i++)
            if (re->rom[i] == 0xA9 && re->rom[i + 3] == 0x99 && re->rom[i + 4] == 0x26 &&
                re->rom[i + 5] == 0x00 && (i & 0xFF0000) == lo) {
                uint32_t eo = lo | re->rom[i + 1] | re->rom[i + 2] << 8;
                if (SpriteLen(re, eo))
                    eu_sites[neu++] = i + 1;
            }
        uint32_t usa_sorted[16];
        for (int k = 0; k < st->npro; k++)
            usa_sorted[k] = st->pro_site[k];
        for (int k = 0; k < st->npro; k++)
            for (int j = k + 1; j < st->npro; j++)
                if (usa_sorted[j] < usa_sorted[k]) {
                    uint32_t t = usa_sorted[k];
                    usa_sorted[k] = usa_sorted[j];
                    usa_sorted[j] = t;
                }
        for (int k = 0; space && k < st->npro; k++) {
            /* European LDA #imm: same script bytes before it, else by order. */
            uint32_t site = FindByContext(ru, re, st->pro_site[k], 9, 2, 0);
            if (!site && neu == st->npro)
                for (int q = 0; q < st->npro; q++)
                    if (usa_sorted[q] == st->pro_site[k])
                        site = eu_sites[q];
            if (!site)
                continue;
            uint32_t eo = (site & 0xFF0000) | Rd16(re, site);
            uint32_t n = SpriteLen(re, eo);
            if (!n || fill + n > cap)
                continue;
            memcpy(space + fill, re->rom + eo, n);
            uint32_t at = st->free_start + fill;
            const uint8_t imm[2] = {(uint8_t)at, (uint8_t)(at >> 8)};
            AddPatch(pack, st->pro_site[k], imm, 2);
            fill += n;
            pro++;
        }
        if (space && fill)
            AddPatch(pack, st->free_start, space, fill);
        free(space);
    }
    pack->sprite_translated = maps + pro;
}

/* ---- menu/item text (ASCII engine) ---------------------------------------- */

/* Argument sizes of ASCII commands $01-$11 ($0C ESC is $FF-delimited). */
static const uint8_t kAsciiArgs[18][3] = {
    [1] = {1, 1}, [2] = {3}, [3] = {1}, [4] = {3, 2}, [5] = {1, 2}, [6] = {1, 1, 2},
    [7] = {2}, [8] = {1, 2}, [14] = {2}, [15] = {1, 1}, [16] = {1},
};
enum { A_PRT = 2, A_PTR = 4, A_ESC = 12, A_LU = 16 };

typedef struct {
    Rom rom;
    uint32_t engine, lu;
} AsciiRom;

static const uint8_t kAsciiEngineSig[] = {0x08, 0x8b, 0xe2, 0x20, 0xb9, 0x00, 0x00, 0xc8, 0xc9, 0x12, 0xb0};

static int AsciiInit(AsciiRom *a, const Rom *r)
{
    a->rom = *r;
    a->engine = a->lu = 0;
    for (size_t i = 0; i + sizeof(kAsciiEngineSig) < r->size; i++)
        if (!memcmp(r->rom + i, kAsciiEngineSig, sizeof(kAsciiEngineSig))) {
            a->engine = (uint32_t)i;
            break;
        }
    if (!a->engine)
        return 0;
    /* JSR (table,X) operand at +$15; entry $10 is [LU]: SEP #$20 / LDA #bank /
     * PHA / PLB / REP #$20 / (PLY) / LDA table,Y. */
    uint32_t table = (a->engine & 0xFF0000) | Rd16(r, a->engine + 0x15);
    uint32_t h = (a->engine & 0xFF0000) | Rd16(r, table + 2 * A_LU);
    for (uint32_t i = h; i < h + 40 && i + 12 < r->size; i++) {
        const uint8_t *p = r->rom + i;
        if (p[0] == 0xE2 && p[1] == 0x20 && p[2] == 0xA9 && p[4] == 0x48 && p[5] == 0xAB &&
            p[6] == 0xC2 && p[7] == 0x20) {
            int k = p[8] == 0x7A ? 9 : 8;
            if (p[k] == 0xB9) {
                a->lu = ((uint32_t)(p[3] & 0x3F) << 16) | p[k + 1] | p[k + 2] << 8;
                break;
            }
        }
    }
    return a->lu != 0;
}

static uint32_t Off24(uint32_t a) { return ((a >> 16) & 0x3F) << 16 | (a & 0xFFFF); }

/* Decode one menu string ([LU] expanded). 0 on anything that is not one. */
static int AsciiDecodeSpan(const AsciiRom *a, uint32_t off, Toks *out, int depth,
                           uint32_t *span)
{
    const Rom *r = &a->rom;
    for (uint32_t i = off; i < r->size && i - off < 512;) {
        Tok t = {0};
        t.ref = -1;
        uint8_t b = r->rom[i++];
        if (b == 0) {
            if (span)
                *span = i - off;
            return 1;
        }
        if (b >= 0x12) {
            t.type = T_GLYPH;
            t.code = b;
            Push(out, &t);
            continue;
        }
        t.type = T_CMD;
        t.code = b;
        if (b == A_ESC) {
            while (i < r->size && r->rom[i] != 0xFF && t.blen < sizeof(t.bin))
                t.bin[t.blen++] = r->rom[i++];
            if (i >= r->size || r->rom[i] != 0xFF)
                return 0;
            i++;
            Push(out, &t);
            continue;
        }
        if (b == 9 || b == 10 || b == 11 || b == 13 || b == 17 || kAsciiArgs[b][0]) {
            for (int k = 0; k < 3; k++) {
                uint32_t v = 0;
                if (i + kAsciiArgs[b][k] > r->size)
                    return 0;
                for (int j = 0; j < kAsciiArgs[b][k]; j++)
                    v |= (uint32_t)r->rom[i + j] << (8 * j);
                i += kAsciiArgs[b][k];
                t.a[k] = v;
            }
        } else {
            return 0;
        }
        if (b == A_LU && depth < 3) {
            uint32_t w = (a->lu & 0xFF0000) | Rd16(r, a->lu + 2 * t.a[0]);
            if (!AsciiDecodeSpan(a, w, out, depth + 1, NULL))
                return 0;
            continue;
        }
        Push(out, &t);
    }
    return 0;
}

static int AsciiDecode(const AsciiRom *a, uint32_t off, Toks *out, int depth)
{
    return AsciiDecodeSpan(a, off, out, depth, NULL);
}

static int AsciiEncode(const Toks *v, uint8_t *out)
{
    int n = 0;
    for (int i = 0; i < v->n; i++) {
        const Tok *t = &v->t[i];
        if (out)
            out[n] = t->code;
        n++;
        if (t->type == T_GLYPH)
            continue;
        if (t->code == A_ESC) {
            if (out)
                memcpy(out + n, t->bin, t->blen), out[n + t->blen] = 0xFF;
            n += t->blen + 1;
            continue;
        }
        for (int k = 0; k < 3; k++)
            for (int j = 0; j < kAsciiArgs[t->code][k]; j++) {
                if (out)
                    out[n] = (uint8_t)(t->a[k] >> (8 * j));
                n++;
            }
    }
    if (out)
        out[n] = 0;
    return n + 1;
}

static int IsAsciiRef(const Tok *t) { return t->type == T_CMD && (t->code == A_PRT || t->code == A_PTR); }

static int AsciiSkelEq(const Toks *a, const Toks *b)
{
    int i = 0, j = 0;
    for (;;) {
        while (i < a->n && a->t[i].type != T_CMD) i++;
        while (j < b->n && b->t[j].type != T_CMD) j++;
        if (i >= a->n || j >= b->n)
            return i >= a->n && j >= b->n;
        if (a->t[i++].code != b->t[j++].code)
            return 0;
    }
}

static int AsciiIndex(const Structure *st, uint32_t off)
{
    for (int i = 0; i < st->nascii; i++)
        if (st->ascii[i] == off)
            return i;
    return -1;
}

/* Pair the menu strings, relocate the European ones into new virtual banks
 * and redirect each USA string with [PRT:@virtual][$00]. Tables stay in ROM:
 * they point at string starts, which are redirected themselves. */
static void AddAscii(const Structure *st, const Rom *ru, const Rom *re, IogPack *pack)
{
    AsciiRom au, ae;
    if (!st->nascii || !AsciiInit(&au, ru) || !AsciiInit(&ae, re)) {
        fprintf(stderr, "[i18n] menu text engine not found; menus stay in English\n");
        return;
    }
    const int n = st->nascii;
    uint32_t *eu_of = calloc((size_t)n, sizeof(uint32_t));
    int *has = calloc((size_t)n, sizeof(int));

    /* COP BD <string24> call sites. */
    Site *us = calloc(4096, sizeof(Site)), *es = calloc(4096, sizeof(Site));
    int nus = 0, nes = 0;
    for (size_t i = 16; i + 16 < ru->size && nus < 4096; i++)
        if (ru->rom[i] == 0x02 && ru->rom[i + 1] == 0xBD) {
            uint32_t t = Off24(ru->rom[i + 2] | ru->rom[i + 3] << 8 | (uint32_t)ru->rom[i + 4] << 16);
            int ai = AsciiIndex(st, t);
            if (ai >= 0)
                us[nus++] = (Site){(uint32_t)i, t, 0xBD, ai};
        }
    Text *ut = calloc((size_t)nus + 1, sizeof(Text));
    for (int i = 0; i < nus; i++)
        AsciiDecode(&au, us[i].target, &ut[i].toks, 0);
    Text *et = calloc(4096, sizeof(Text));
    for (size_t i = 16; i + 16 < re->size && nes < 4096; i++)
        if (re->rom[i] == 0x02 && re->rom[i + 1] == 0xBD) {
            uint32_t t = Off24(re->rom[i + 2] | re->rom[i + 3] << 8 | (uint32_t)re->rom[i + 4] << 16);
            Toks v = {0};
            if (AsciiDecode(&ae, t, &v, 0) && v.n) {
                et[nes].toks = v;
                es[nes] = (Site){(uint32_t)i, t, 0xBD, nes};
                nes++;
            } else {
                free(v.t);
            }
        }
    int *best = calloc((size_t)(nus + 1) * (size_t)(nes + 1), sizeof(int));
    uint8_t *move = calloc((size_t)(nus + 1) * (size_t)(nes + 1), 1);
#define B(i, j) best[(size_t)(i) * (size_t)(nes + 1) + (size_t)(j)]
#define M(i, j) move[(size_t)(i) * (size_t)(nes + 1) + (size_t)(j)]
    for (int i = 1; i <= nus; i++)
        for (int j = 1; j <= nes; j++) {
            int v = B(i - 1, j), mv = 1;
            if (B(i, j - 1) > v)
                v = B(i, j - 1), mv = 2;
            int sc = 0;
            for (int k = 1; k <= 8; k++)
                sc += ru->rom[us[i - 1].off - k] == re->rom[es[j - 1].off - k];
            for (int k = 5; k < 11; k++)
                sc += ru->rom[us[i - 1].off + k] == re->rom[es[j - 1].off + k];
            if (AsciiSkelEq(&ut[i - 1].toks, &et[j - 1].toks))
                sc += 6;
            if (sc >= 10 && B(i - 1, j - 1) + sc > v)
                v = B(i - 1, j - 1) + sc, mv = 3;
            B(i, j) = v;
            M(i, j) = (uint8_t)mv;
        }
    for (int i = nus, j = nes; i && j;) {
        if (M(i, j) == 3) {
            int ai = us[i - 1].li;
            if (!has[ai])
                eu_of[ai] = es[j - 1].target, has[ai] = 1;
            i--, j--;
        } else if (M(i, j) == 1) {
            i--;
        } else {
            j--;
        }
    }
#undef B
#undef M

    /* Follow [PRT] strings and [PTR] tables in step. */
    for (int changed = 1; changed;) {
        changed = 0;
        for (int ai = 0; ai < n; ai++) {
            if (!has[ai])
                continue;
            Toks u = {0}, e = {0};
            if (AsciiDecode(&au, st->ascii[ai], &u, 0) && AsciiDecode(&ae, eu_of[ai], &e, 0)) {
                for (int x = 0, y = 0;; x++, y++) {
                    while (x < u.n && !IsAsciiRef(&u.t[x])) x++;
                    while (y < e.n && !IsAsciiRef(&e.t[y])) y++;
                    if (x >= u.n || y >= e.n || u.t[x].code != e.t[y].code)
                        break;
                    uint32_t uo = Off24(u.t[x].a[0]), eo = Off24(e.t[y].a[0]);
                    if (u.t[x].code == A_PRT) {
                        int k = AsciiIndex(st, uo);
                        if (k >= 0 && !has[k])
                            eu_of[k] = eo, has[k] = 1, changed = 1;
                        continue;
                    }
                    for (int q = 0; q < st->nptab; q++) {
                        if (st->ptab[q] != uo)
                            continue;
                        for (int k = 0; k < st->ptab_n[q]; k++) {
                            uint32_t ue = (uo & 0xFF0000) | Rd16(ru, uo + 2 * (uint32_t)k);
                            uint32_t ee = (eo & 0xFF0000) | Rd16(re, eo + 2 * (uint32_t)k);
                            int ki = AsciiIndex(st, ue);
                            if (ki >= 0 && !has[ki])
                                eu_of[ki] = ee, has[ki] = 1, changed = 1;
                        }
                    }
                }
            }
            free(u.t);
            free(e.t);
        }
    }

    /* Relocate and redirect. */
    uint32_t ends[4096];
    int nends = 0;
    for (int i = 0; i < st->nl && nends < 4096; i++) ends[nends++] = st->l[i].off;
    for (int i = 0; i < n && nends < 4096; i++) ends[nends++] = st->ascii[i];
    for (int i = 0; i < st->nt && nends < 4096; i++) ends[nends++] = st->t[i].off;
    for (int i = 0; i < st->nptab && nends < 4096; i++) ends[nends++] = st->ptab[i];
    int vb = -1, fill = kIogVirtualBankSize, done = 0;
    for (int ai = 0; ai < n; ai++) {
        if (!has[ai]) {
            if (getenv("IOG_I18N_REPORT"))
                fprintf(stderr, "[i18n] menu untranslated %06X (no pair)\n", st->ascii[ai]);
            continue;
        }
        uint32_t off = st->ascii[ai], next = off + 0x10000;
        for (int k = 0; k < nends; k++)
            if (ends[k] > off && ends[k] < next)
                next = ends[k];
        if (next - off < 5) {
            if (getenv("IOG_I18N_REPORT"))
                fprintf(stderr, "[i18n] menu untranslated %06X (only %u bytes)\n", off, next - off);
            continue;
        }
        Toks u = {0}, e = {0};
        int ok = AsciiDecode(&au, off, &u, 0) && AsciiDecode(&ae, eu_of[ai], &e, 0);
        /* Drawn tile runs ([ESC], e.g. the HUD's PLAYER label) must match:
         * where the European release draws them elsewhere, the USA string
         * with the European font already shows the European art. */
        int ue = 0, ee = 0;
        for (int k = 0; k < u.n; k++) ue += u.t[k].type == T_CMD && u.t[k].code == A_ESC;
        for (int k = 0; k < e.n; k++) ee += e.t[k].type == T_CMD && e.t[k].code == A_ESC;
        if (ok && ue != ee && pack->has_font) {
            /* Keep the USA string (with the European font it shows the
             * European art), completing drawn runs from the European HUD. */
            free(e.t);
            e = (Toks){0};
            for (int k = 0; k < u.n; k++) {
                Tok t = u.t[k];
                if (t.type == T_CMD && t.code == A_ESC && t.blen) {
                    int run = 1;
                    for (int q = 1; q < t.blen; q++)
                        run &= t.bin[q] == t.bin[q - 1] + 1;
                    /* The European HUD is a plain tilemap in ROM (tile | $3400
                     * words); where it holds the same run, the tiles that
                     * follow it complete the label (JUGADO + R). */
                    uint8_t pat[2 * sizeof(t.bin)];
                    int np = 0;
                    for (int q = 0; q < t.blen; q++)
                        pat[np++] = t.bin[q], pat[np++] = 0x34;
                    for (size_t i = 0; run && np && i + (size_t)np + 2 < re->size; i++) {
                        if (memcmp(re->rom + i, pat, (size_t)np))
                            continue;
                        for (size_t w = i + (size_t)np; w + 1 < re->size && re->rom[w] &&
                             re->rom[w + 1] == 0x34 && t.blen < sizeof(t.bin); w += 2)
                            t.bin[t.blen++] = re->rom[w];
                        break;
                    }
                }
                Push(&e, &t);
            }
        } else {
            ok &= ue == ee;
        }
        /* The European references become the USA ones, in order. */
        for (int x = 0, y = 0; ok; x++, y++) {
            while (x < u.n && !IsAsciiRef(&u.t[x])) x++;
            while (y < e.n && !IsAsciiRef(&e.t[y])) y++;
            if (x >= u.n && y >= e.n)
                break;
            if (x >= u.n || y >= e.n || u.t[x].code != e.t[y].code) {
                ok = 0;
                break;
            }
            e.t[y].a[0] = u.t[x].a[0];
        }
        int len = ok ? AsciiEncode(&e, NULL) : 0;
        if (ok && len <= kIogVirtualBankSize) {
            if (fill + len > kIogVirtualBankSize) {
                if (pack->nbanks >= kIogVirtualBanks)
                    ok = 0;
                else {
                    vb = pack->nbanks++;
                    pack->banks[vb] = calloc(1, kIogVirtualBankSize);
                    fill = 0;
                }
            }
            if (ok) {
                AsciiEncode(&e, pack->banks[vb] + fill);
                uint32_t addr = ((uint32_t)(kVBankFirst + vb) << 16) | (kVBase + (uint32_t)fill);
                AddRedirect(pack, off, A_PRT, addr, 0);
                fill += len;
                done++;
            }
        }
        if (!ok && getenv("IOG_I18N_REPORT"))
            fprintf(stderr, "[i18n] menu untranslated %06X (differs, %d/%d drawn runs)\n", off, ue, ee);
        free(u.t);
        free(e.t);
    }
    pack->menu_translated = done;
    pack->menu_total = n;
    for (int i = 0; i < nus; i++) free(ut[i].toks.t);
    for (int i = 0; i < nes; i++) free(et[i].toks.t);
    free(ut); free(et); free(us); free(es); free(best); free(move); free(eu_of); free(has);
}

/* ---- build ---------------------------------------------------------------------- */

void IogTextFreePack(IogPack *p)
{
    if (!p)
        return;
    for (int i = 0; i < p->nbanks; i++)
        free(p->banks[i]);
    for (int i = 0; i < p->npatches; i++) {
        free(p->patches[i].data);
        free(p->patches[i].original);
    }
    free(p->patches);
    free(p);
}

static int CountRefs(const Toks *v, uint8_t *codes, int max)
{
    int n = 0;
    for (int i = 0; i < v->n; i++)
        if (v->t[i].type == T_CMD && IsRef(v->t[i].code)) {
            if (n < max)
                codes[n] = v->t[i].code;
            n++;
        }
    return n;
}

/* Replace a European string's references by the USA string's, in order, and
 * put the [::] marker after the same number of line/page breaks. */
static int AdoptUsaStructure(const Toks *usa, Toks *eu)
{
    uint8_t uc[32], ec[32];
    int nu = CountRefs(usa, uc, 32), ne = CountRefs(eu, ec, 32);
    if (nu != ne || nu > 32 || memcmp(uc, ec, (size_t)nu))
        return 0;
    int k = 0;
    for (int i = 0; i < eu->n; i++)
        if (eu->t[i].type == T_CMD && IsRef(eu->t[i].code)) {
            int seen = 0;
            for (int j = 0; j < usa->n; j++)
                if (usa->t[j].type == T_CMD && IsRef(usa->t[j].code) && seen++ == k) {
                    eu->t[i] = usa->t[j];
                    break;
                }
            k++;
        }
    int breaks = -1;
    for (int j = 0, b = 0; j < usa->n; j++) {
        if (usa->t[j].type == T_MARK) {
            breaks = b;
            break;
        }
        b += usa->t[j].type == T_CMD && (usa->t[j].code == CMD_N || usa->t[j].code == CMD_FIN);
    }
    if (breaks >= 0) {
        int at = eu->n, b = 0;
        for (int i = 0; i < eu->n; i++) {
            if (b == breaks) {
                at = i;
                break;
            }
            b += eu->t[i].type == T_CMD && (eu->t[i].code == CMD_N || eu->t[i].code == CMD_FIN);
        }
        Tok mk = {0};
        mk.type = T_MARK;
        mk.ref = -1;
        Push(eu, &mk);
        memmove(&eu->t[at + 1], &eu->t[at], (size_t)(eu->n - 1 - at) * sizeof(Tok));
        eu->t[at] = mk;
    }
    return 1;
}

/* Lay out every label's final text into virtual banks and redirects.
 * tr/has: translated tokens per label (European ROM text when `adopt`,
 * which then takes the USA string's references and marker; a community
 * translation already names them). Consumes the token lists it uses. */
/* A scene title is also measured, by $02:A172, which sizes and centres its
 * box: it counts glyphs, [SKP:n] as n and dictionary words, steps over any
 * other command byte alone and does not follow [PRT]. The stub
 * [PRT:@virtual][SKP:k][RET] makes it measure the new text: the address
 * bytes count as the routine sees them and k makes up the rest (the skip
 * lands after the last letter, so nothing moves on screen). */
static int AddSceneRedirectWidth(IogPack *pack, const Rom *ru, uint32_t off, uint32_t addr,
                                  int width)
{
    uint8_t b[7] = {CMD_PRT, (uint8_t)addr, (uint8_t)(addr >> 8), (uint8_t)(addr >> 16),
                    0xCC, 0, CMD_RET};
    int seen = 0;
    for (int k = 1; k < 4; k++) {
        if (b[k] == CMD_RET || b[k] == 0xCC || b[k] == CMD_LU1 || b[k] == CMD_LU2)
            return 0;                  /* would derail the measure: keep USA text */
        seen += b[k] < 0xC0;
    }
    if (width < seen || width - seen > 0xFF || SceneTitleLen(ru, off) + 1 < sizeof(b))
        return 0;
    b[5] = (uint8_t)(width - seen);
    AddPatch(pack, off, b, sizeof(b));
    return 1;
}

static int AddSceneRedirect(IogPack *pack, const Rom *ru, uint32_t off, uint32_t addr,
                             const Toks *v)
{
    int width = 0;
    for (int k = 0; k < v->n; k++)
        if (v->t[k].type == T_GLYPH)
            width++;
        else if (v->t[k].type == T_CMD && v->t[k].code == 0xCC)
            width += (int)v->t[k].a[0];
    return AddSceneRedirectWidth(pack, ru, off, addr, width);
}


/* ---- hand translations ---------------------------------------------------
 * The few dialogue strings with no counterpart in the European ROM (found by
 * IOG_I18N_REPORT=1) are translated here. The USA string's commands are
 * kept (boxes, colours, pauses, line breaks); only its runs of text are
 * replaced, in order, separated by '|'. Glyph codes: the dialogue font
 * (GaiaLabs' WideString map, shiftType h2); the European fonts put their
 * accents on codes $01-$09 (read off the Spanish ROM). */
typedef struct { const char *ch; uint8_t code; } GlyphMap;
static const GlyphMap kGlyphs[] = { {"0",0x20},{"1",0x21},{"2",0x22},{"3",0x23},{"4",0x24},{"5",0x25},{"6",0x26},{"7",0x27},{"8",0x28},{"9",0x29},{".",0x2A},{",",0x2B},{"\"",0x2D},{":",0x2F},{"A",0x40},{"B",0x41},{"C",0x42},{"D",0x43},{"E",0x44},{"F",0x45},{"G",0x46},{"H",0x47},{"I",0x48},{"J",0x49},{"K",0x4A},{"L",0x4B},{"M",0x4C},{"N",0x4D},{"O",0x4E},{"!",0x4F},{"P",0x60},{"Q",0x61},{"R",0x62},{"S",0x63},{"T",0x64},{"U",0x65},{"V",0x66},{"W",0x67},{"X",0x68},{"Y",0x69},{"Z",0x6A},{"/",0x6B},{"*",0x6C},{"-",0x6D},{"(",0x6E},{")",0x6F},{"a",0x80},{"b",0x81},{"c",0x82},{"d",0x83},{"e",0x84},{"f",0x85},{"g",0x86},{"h",0x87},{"i",0x88},{"j",0x89},{"k",0x8A},{"l",0x8B},{"m",0x8C},{"n",0x8D},{"o",0x8E},{";",0x8F},{"p",0xA0},{"q",0xA1},{"r",0xA2},{"s",0xA3},{"t",0xA4},{"u",0xA5},{"v",0xA6},{"w",0xA7},{"x",0xA8},{"y",0xA9},{"z",0xAA},{" ",0xAC},{"?",0x0D},{"'",0x0E} };
static const GlyphMap kEuGlyphs[] = {
    {"é",0x01},{"á",0x02},{"í",0x03},{"ó",0x04},{"ú",0x05},{"ñ",0x06},{"ü",0x07},{"¿",0x08},{"¡",0x09},
    {"É",0x40|4},{"Á",0x40},{"Í",0x48},{"Ó",0x4E},{"Ú",0x65},
};

static int GlyphFor(const char **ps, uint8_t *out)
{
    for (size_t i = 0; i < sizeof(kEuGlyphs) / sizeof(kEuGlyphs[0]); i++) {
        const size_t n = strlen(kEuGlyphs[i].ch);
        if (!strncmp(*ps, kEuGlyphs[i].ch, n)) { *out = kEuGlyphs[i].code; *ps += n; return 1; }
    }
    for (size_t i = 0; i < sizeof(kGlyphs) / sizeof(kGlyphs[0]); i++)
        if (**ps == kGlyphs[i].ch[0]) { *out = kGlyphs[i].code; (*ps)++; return 1; }
    (*ps)++;
    return 0;
}

static const char *GlyphText(uint8_t code)
{
    for (size_t i = 0; i < sizeof(kGlyphs) / sizeof(kGlyphs[0]); i++)
        if (kGlyphs[i].code == code) return kGlyphs[i].ch;
    return "#";
}

/* Stock templates that set the speaker colours/SFX without moving the cursor
 * or reopening the box. $11 is the stock route menu, not a speaker. */
static int GaiaSpeakerTemplate(unsigned id)
{
    return id < 8 || (id >= 0x12 && id <= 0x15);
}

enum { kGaiaBase, kGaiaSupplement, kGaiaExtended, kGaiaStockAnchors, kGaiaStockLayout,
       kGaiaSharedBox, kGaiaInheritedChoice, kGaiaPairedEntry, kGaiaStockReflow,
       kGaiaTimedReflow };

static int GaiaDialogue(const char *text, Toks *out)
{
    const int extended = !strncmp(text, "[EXT]", 5);
    if (extended)
        text += 5;
    const size_t size = strlen(text);
    const int returns = size >= 5 && !strcmp(text + size - 5, "[RET]");
    const int max_columns = extended ? 26 : 24;
    int columns = 0, rows = 1, glyphs = 0, page_start = 1;
    while (*text) {
        Tok token = {.type = T_CMD, .ref = -1};
        if (extended && glyphs && !strcmp(text, "[JMP:06BF7C]")) {
            token.code = CMD_JMP;
            token.a[0] = 0x06bf7c;
            Push(out, &token);
            return 1;
        } else if (extended && (!strncmp(text, "[CLR]", 5) || !strncmp(text, "[CLD]", 5))) {
            token.code = text[3] == 'R' ? 0xce : 0xc8;
            columns = 0;
            rows = 1;
            text += 5;
        } else if (extended && !strncmp(text, "[PRT:", 5)) {
            unsigned offset;
            int length = 0;
            if (sscanf(text + 5, "%6X]%n", &offset, &length) != 1 ||
                length != 7 || strspn(text + 5, "0123456789ABCDEF") != 6 ||
                (offset != 0x08de96 && offset != 0x069705))
                return 0;
            token.code = CMD_PRT;
            token.a[0] = offset;
            text += 12;
        } else if ((returns || extended) && !strncmp(text, "[BCD:", 5)) {
            unsigned digits, address;
            int length = 0;
            if (sscanf(text, "[BCD:%1u,%4X]%n", &digits, &address, &length) != 2 ||
                length != 12 || strspn(text + 7, "0123456789ABCDEF") != 4 ||
                digits < 1 || digits > 5 || (columns += (int)digits) > max_columns)
                return 0;
            token.code = 0xc6;
            token.a[0] = digits;
            token.a[1] = address;
            text += length;
            glyphs++;
        } else if (extended && (!strncmp(text, "[PAU:", 5) || !strncmp(text, "[PAL:", 5))) {
            unsigned value;
            int length = 0;
            const int pause = text[3] == 'U';
            if (sscanf(text + 5, "%2X]%n", &value, &length) != 1 ||
                length != 3 || strspn(text + 5, "0123456789ABCDEF") != 2 ||
                (pause ? !value : (value & ~0x1cu) != 0))
                return 0;
            token.code = pause ? 0xc9 : 0xc3;
            token.a[0] = value;
            text += 8;
        } else if (extended && !strncmp(text, "[WAI]", 5)) {
            token.code = 0xd0;
            text += 5;
        } else if (returns && !extended && (!strncmp(text, "[PAU:", 5) ||
                              !strncmp(text, "[PAL:", 5) || !strncmp(text, "[TPL:", 5))) {
            return 0;
        } else if (!strncmp(text, "[PAU:", 5)) {
            unsigned frames;
            int length = 0;
            if (sscanf(text, "[PAU:%2X]%n", &frames, &length) != 1 ||
                length != 8 || strspn(text + 5, "0123456789ABCDEF") != 2 || !frames)
                return 0;
            token.type = T_MARK;
            token.code = 0xc9;
            token.a[0] = frames;
            text += length;
            if (!page_start && strncmp(text, "[FIN]", 5) && strcmp(text, "[END]") &&
                strcmp(text, "[PAL:00][END]"))
                return 0;
        } else if (!strcmp(text, "[PAL:00][END]")) {
            if (page_start)
                return 0;
            token.type = T_MARK;
            token.code = 0xc3;
            text += 8;
        } else if (!strncmp(text, "[TPL:", 5)) {
            unsigned id;
            int length = 0;
            if (!page_start || (out->n && out->t[out->n - 1].type == T_MARK) ||
                sscanf(text, "[TPL:%2X]%n", &id, &length) != 1 ||
                length != 8 || strspn(text + 5, "0123456789ABCDEF") != 2 ||
                !GaiaSpeakerTemplate(id))
                return 0;
            token.type = T_MARK;
            token.a[0] = id;
            text += length;
        } else if (!strncmp(text, "[N]", 3)) {
            token.code = CMD_N;
            text += 3;
            columns = 0;
            if (++rows > (extended || returns ? 7 : 3))
                return 0;
        } else if (!strncmp(text, "[FIN]", 5)) {
            token.code = CMD_FIN;
            text += 5;
            columns = 0;
            rows = 1;
        } else if ((!returns && !strcmp(text, "[END]")) ||
                   (returns && !strcmp(text, "[RET]"))) {
            token.code = returns ? CMD_RET : CMD_END;
            Push(out, &token);
            return glyphs != 0;
        } else {
            token.type = T_GLYPH;
            if ((unsigned char)*text >= 128 || !GlyphFor(&text, &token.code) || ++columns > max_columns)
                return 0;
            glyphs++;
        }
        Push(out, &token);
        /* A speaker tag may be followed by a pause before the first glyph. */
        page_start = (token.type == T_CMD && token.code == CMD_FIN) ||
                     (token.type == T_MARK && !token.code) ||
                     (extended && token.type == T_CMD &&
                      (token.code == 0xce || token.code == 0xc8 ||
                       (page_start && (token.code == 0xc9 || token.code == 0xc3))));
    }
    return 0;
}

/* Accept a speaker change only where stock does so at a finished page.
 * The upstream text must identify the complete stock speaker sequence. */
static int GaiaSpeakerSequenceMatches(const Toks *original, const Toks *text)
{
    int candidate = 0;
    for (int i = 0; i < original->n; i++) {
        const Tok *token = &original->t[i];
        if (token->type != T_CMD || token->code != 0xc2 ||
            !GaiaSpeakerTemplate(token->a[0]))
            continue;
        while (candidate < text->n && text->t[candidate].type != T_MARK)
            candidate++;
        if (candidate == text->n || text->t[candidate++].a[0] != token->a[0])
            return 0;
    }
    for (; candidate < text->n; candidate++)
        if (text->t[candidate].type == T_MARK)
            return 0;
    return 1;
}

static int GaiaSoftBreak(const Tok *token)
{
    return token->type == T_CMD || token->code == 0xac;
}

/* Reflow only pages that exceed their stock box height. Treat the source
 * line breaks as spaces so, for example, the last word of a sentence does
 * not become a page by itself when it can fit in the current box. */
static int GaiaWrapPage(const Tok *start, const Tok *end, Toks *out, int width,
                        int height, int allow_extra_pages)
{
    int columns = 0, rows = 1;
    while (start < end) {
        while (start < end && GaiaSoftBreak(start))
            start++;
        const Tok *word = start;
        while (start < end && !GaiaSoftBreak(start))
            start++;
        int length = (int)(start - word);
        if (!length)
            break;
        if (length > width)
            return 0;
        if (columns) {
            Tok gap = {.type = T_GLYPH, .code = 0xac, .ref = -1};
            if (columns + 1 + length > width) {
                gap.type = T_CMD;
                gap.code = ++rows > height ? CMD_FIN : CMD_N;
                if (gap.code == CMD_FIN) {
                    if (!allow_extra_pages)
                        return 0;
                    rows = 1;
                }
                columns = 0;
            } else {
                columns++;
            }
            Push(out, &gap);
        }
        while (word < start)
            Push(out, word++);
        columns += length;
    }
    return columns > 0;
}

static int GaiaFitPage(const Tok *start, const Tok *end, Toks *out,
                       int width, int height, int reflow_allowed)
{
    int columns = 0, rows = 1, has_glyph = 0;
    for (const Tok *token = start; token < end; token++) {
        if (token->type == T_CMD) {
            columns = 0;
            rows++;
        } else {
            columns++;
            has_glyph |= token->code != 0xac;
            if (columns > width)
                return 0;
        }
    }
    if (rows > height)
        return reflow_allowed && GaiaWrapPage(start, end, out, width, height, 1);
    if (!has_glyph)
        return 0;
    while (start < end)
        Push(out, start++);
    return 1;
}

static int GaiaPageText(const Tok *token)
{
    return token->type == T_GLYPH || (token->type == T_CMD && token->code == CMD_N);
}

/* An inherited box has no explicit dimensions in this string. Its original
 * text is a conservative bound: keep the same page boundaries and never
 * extend a translated page past the authored rows or longest line. */
static void GaiaInheritedPageBounds(const Tok *start, const Tok *end,
                                    int *width, int *height)
{
    int columns = 0;
    *width = 0;
    *height = 1;
    for (; start < end; start++) {
        if (start->type == T_GLYPH) {
            if (++columns > *width)
                *width = columns;
        } else {
            columns = 0;
            ++*height;
        }
    }
}

static const uint8_t kGaiaTemplateRows[] = {1, 2, 3, 4, 1, 2, 3, 4, 4};

static int GaiaFragmentText(const Tok *token)
{
    return token->type == T_GLYPH || (token->type == T_CMD && token->code == 0xc6);
}

static int GaiaFragmentColumns(const Tok *start, const Tok *end)
{
    int columns = 0;
    for (; start < end; start++)
        columns += start->type == T_GLYPH ? 1 : (int)start->a[0];
    return columns;
}

/* A returning fragment can be an interactive prompt. Keep the exact
 * number of rows/pages, indentation, stock layout and command sequence.
 * Never turn its RET into END or relocate any control-flow target. */
static int GaiaStockReturnRows(const Toks *stock, Toks *out, const Toks *text, int measured)
{
    int src = 0, dst = 0, width = 0, height = 0, row = 1, speaker = -1;
    while (src < stock->n && dst < text->n) {
        while (src < stock->n && !GaiaFragmentText(&stock->t[src])) {
            const Tok *t = &stock->t[src];
            if (t->type != T_CMD)
                return 0;
            if (t->code == CMD_N || t->code == CMD_FIN || t->code == CMD_RET)
                break;
            switch (t->code) {
            case 0xc2:
                if (t->a[0] >= 8 && t->a[0] <= 0x10) {
                    width = measured ? 26 : 24;
                    height = kGaiaTemplateRows[t->a[0] - 8];
                } else if (!GaiaSpeakerTemplate(t->a[0])) {
                    return 0;
                } else {
                    speaker = (int)t->a[0];
                }
                break;
            case 0xc7:
                width = (int)t->a[0] * 2 - (measured ? 0 : 2);
                height = (int)t->a[1];
                break;
            case 0xd3:
                width = measured ? 26 : 24;
                height = 4;
                break;
            case 0xc8:
                if (measured)
                    width = height = 0;
                break;
            case 0xc1: case 0xc3: case 0xc9:
            case 0xce: case 0xd0: case CMD_SFX: case 0xd5:
                break;
            default:
                return 0;
            }
            Push(out, t);
            src++;
        }
        if (measured && dst < text->n && text->t[dst].type == T_MARK &&
            !text->t[dst].code && speaker == (int)text->t[dst].a[0])
            ++dst;
        const int sstart = src, dstart = dst;
        while (src < stock->n && GaiaFragmentText(&stock->t[src]))
            src++;
        while (dst < text->n && GaiaFragmentText(&text->t[dst]))
            dst++;
        if ((src == sstart) != (dst == dstart) || (height && row > height))
            return 0;
        const int original_width = GaiaFragmentColumns(stock->t + sstart, stock->t + src);
        const int translated_width = GaiaFragmentColumns(text->t + dstart, text->t + dst);
        int si = sstart, di = dstart;
        while (si < src && stock->t[si].code == 0xac)
            si++;
        while (di < dst && text->t[di].code == 0xac)
            di++;
        const int indentation = si - sstart - (di - dstart);
        if ((!measured && indentation) ||
            translated_width + (measured ? indentation : 0) > (width ? width : original_width))
            return 0;
        const int content_start = di;
        for (;;) {
            while (si < src && stock->t[si].type == T_GLYPH)
                si++;
            while (di < dst && text->t[di].type == T_GLYPH)
                di++;
            if (si == src || di == dst) {
                if (si != src || di != dst)
                    return 0;
                break;
            }
            if (stock->t[si].a[0] != text->t[di].a[0] ||
                stock->t[si].a[1] != text->t[di].a[1])
                return 0;
            si++;
            di++;
        }
        if (measured)
            for (int i = sstart; i < sstart + content_start - dstart + indentation; ++i)
                Push(out, &stock->t[i]);
        for (int i = measured ? content_start : dstart; i < dst; i++)
            Push(out, &text->t[i]);
        if (src == stock->n || dst == text->n)
            return 0;
        while (src < stock->n && stock->t[src].type == T_CMD &&
               (stock->t[src].code == 0xc3 || stock->t[src].code == 0xc8 ||
                stock->t[src].code == 0xc9 || stock->t[src].code == 0xd0))
            Push(out, &stock->t[src++]);
        if (src == stock->n || stock->t[src].type != T_CMD ||
            text->t[dst].type != T_CMD || stock->t[src].code != text->t[dst].code)
            return 0;
        const uint8_t delimiter = stock->t[src].code;
        if (delimiter != CMD_N && delimiter != CMD_FIN && delimiter != CMD_RET)
            return 0;
        row = delimiter == CMD_N ? row + 1 : 1;
        Push(out, &stock->t[src++]);
        dst++;
    }
    return src == stock->n && dst == text->n &&
           stock->t[src - 1].code == CMD_RET;
}

static int GaiaStockReturn(const Toks *stock, Toks *out, const Toks *text)
{
    return GaiaStockReturnRows(stock, out, text, 0);
}

/* Extended rows keep the original interpreter command stream and its row
 * boundaries. New timed or dynamic controls must match a stock command with
 * the same operands, between the same runs of printable text. */
static int GaiaStockExactRows(const Toks *stock, Toks *out, const Toks *text,
                              int measured_layout)
{
    int src = 0, dst = 0, width = 0, height = 0, row = 1, column = 0;
    unsigned left = 0, top = 0;
    const int returning = text->t[text->n - 1].code == CMD_RET;
    while (src < stock->n && dst < text->n) {
        const Tok *original = &stock->t[src];
        const Tok *replacement = &text->t[dst];
        if (original->type == T_GLYPH) {
            const int start = src, first = dst;
            while (src < stock->n && stock->t[src].type == T_GLYPH)
                src++;
            while (dst < text->n && text->t[dst].type == T_GLYPH)
                dst++;
            if (dst == first || (!width && dst - first > src - start))
                return 0;
            if (returning && !column) {
                int si = start, di = first;
                while (si < src && stock->t[si].code == 0xac)
                    si++;
                while (di < dst && text->t[di].code == 0xac)
                    di++;
                if (si - start != di - first)
                    return 0;
            }
            column += dst - first;
            for (int i = first; i < dst; i++)
                Push(out, &text->t[i]);
        } else {
            const unsigned code = original->code;
            if (original->type != T_CMD)
                return 0;
            const int matches = replacement->type == T_CMD && replacement->code == code &&
                                replacement->a[0] == original->a[0] &&
                                replacement->a[1] == original->a[1];
            switch (code) {
            case 0xc1:
                if (column)
                    return 0;
                left = original->a[0];
                top = original->a[1];
                width = height = 0;
                break;
            case 0xc7:
                if (column || original->a[0] < 2 || original->a[1] < 1 ||
                    !left || !top || left + 2 * original->a[0] > 33 ||
                    top + 2 * original->a[1] > 31)
                    return 0;
                width = (int)original->a[0] * 2 - (measured_layout ? 0 : 2);
                height = (int)original->a[1];
                row = 1;
                break;
            case 0xc2: {
                unsigned id = original->a[0];
                if (column)
                    return 0;
                if (GaiaSpeakerTemplate(id)) {
                    if (replacement->type == T_MARK && !replacement->code) {
                        if (id != replacement->a[0])
                            return 0;
                        dst++;
                    }
                } else if (id >= 8 && id <= 0x10) {
                    width = measured_layout ? 26 : 24;
                    height = kGaiaTemplateRows[id - 8];
                    row = 1;
                } else {
                    return 0;
                }
                break;
            }
            case 0xd3:
                if (column)
                    return 0;
                width = measured_layout ? 26 : 24;
                height = 4;
                row = 1;
                break;
            case 0xc3:
                dst += matches;
                break;
            case 0xc8: case 0xce:
                if (measured_layout && matches) {
                    column = 0;
                    row = 1;
                    if (code == 0xc8)
                        width = height = 0;
                    dst++;
                    break;
                }
                if (column)
                    return 0;
                break;
            case CMD_SFX: case 0xd5:
                if (column)
                    return 0;
                break;
            case 0xc6:
                if (!matches || original->a[0] < 1 || original->a[0] > 5)
                    return 0;
                column += (int)original->a[0];
                dst++;
                break;
            case 0xc9: case 0xd0:
                if (!matches)
                    return 0;
                dst++;
                break;
            case CMD_N: case CMD_FIN: case CMD_RET: case CMD_END:
                if (!matches)
                    return 0;
                column = 0;
                row = code == CMD_N ? row + 1 : 1;
                dst++;
                break;
            default:
                return 0;
            }
            Push(out, original);
            src++;
        }
        if ((width && column > width) || (height && column && row > height))
            return 0;
    }
    return src == stock->n && dst == text->n;
}

/* A standalone prose box can reflow without moving script commands. Its
 * authored page breaks still cap an inherited box, where the caller's
 * dimensions are unknown. An explicit box can insert manual page waits. */
typedef struct {
    int width, height;
    int allow_phase_reflow;
    int allow_inherited_reflow;
} GaiaBoxState;

static int GaiaStockProse(const Toks *stock, Toks *out, const Toks *text,
                          int allow_stock_calls, int measured_layout, GaiaBoxState *box)
{
    const int sn = stock->n, tn = text->n;
    if (!sn || !tn || stock->t[sn - 1].code != text->t[tn - 1].code)
        return 0;
    const int returning = stock->t[sn - 1].code == CMD_RET;
    /* A wait and clear immediately before RET leaves no drawn choice rows
     * for the caller. Keep this final wait and every preceding page wait. */
    if (returning && (sn < 3 || tn < 3 || stock->t[sn - 2].code != CMD_FIN ||
                      text->t[tn - 2].code != CMD_FIN))
        return 0;
    if (!returning && stock->t[sn - 1].code != CMD_END)
        return 0;
    int start = 0, width = box ? box->width : 0, height = box ? box->height : 0;
    int speaker = -1, position = 0;
    uint32_t call = 0;
    while (start < sn && !GaiaPageText(&stock->t[start])) {
        const Tok *t = &stock->t[start++];
        switch (t->code) {
        case 0xc1:
            if (position)
                return 0;
            position = 1;
            break;
        case 0xc7:
            width = (int)t->a[0] * 2 - (measured_layout ? 0 : 2);
            height = (int)t->a[1];
            position = 0;
            break;
        case 0xc2:
            if (GaiaSpeakerTemplate(t->a[0])) {
                if (speaker >= 0)
                    return 0;
                speaker = (int)t->a[0];
            } else if (t->a[0] >= 8 && t->a[0] <= 0x10) {
                width = measured_layout ? 26 : 24;
                height = kGaiaTemplateRows[t->a[0] - 8];
            } else {
                return 0;
            }
            break;
        case 0xd3:
            width = measured_layout ? 26 : 24;
            height = 4;
            break;
        case CMD_PRT:
            if (!allow_stock_calls || call || position)
                return 0;
            if (t->a[0] == 0x88de96 && !width && !height) {
                /* This Dark Space prefix opens and clears its four-row box. */
                width = 24;
                height = 4;
            } else if (t->a[0] != 0x869705 || width != 24 || height != 3) {
                return 0;
            }
            /* Both stock callees finish with FIN then RET. The original call
             * and bank are preserved, including the existing prefix overlay. */
            call = t->a[0] & 0x3fffff;
            break;
        case 0xc8:
            if (box)
                width = height = 0;
            break;
        case 0xc3: case 0xce: case CMD_SFX: case 0xd5:
            break;
        default:
            return 0;
        }
        Push(out, t);
    }
    if (position || (allow_stock_calls && !call))
        return 0;
    if (box) {
        box->width = width;
        box->height = height;
    }
    const int inherited = width == 0 && height == 0;
    int end = sn - (returning ? 2 : 1);
    if (!returning && end > start &&
        stock->t[end - 1].type == T_CMD && stock->t[end - 1].code == 0xc3)
        end--;
    int pages = 1, stock_width = 0, stock_height = 0, row = 1, column = 0;
    for (int i = start; i <= end; i++) {
        const Tok *t = &stock->t[i];
        if (i < end && t->type == T_GLYPH) {
            if (++column > stock_width)
                stock_width = column;
        } else if (i < end && t->type == T_CMD && t->code == CMD_N) {
            column = 0;
            row++;
        } else if (i == end || (t->type == T_CMD && t->code == CMD_FIN)) {
            if (row > stock_height)
                stock_height = row;
            row = 1;
            column = 0;
            pages += i < end;
        } else {
            return 0;
        }
    }
    if (inherited) {
        width = stock_width;
        height = stock_height;
    }
    if (width < 1 || width > 26 || height < 1 || height > 7)
        return 0;
    int first = 0;
    if (text->t[first].type == T_MARK && !text->t[first].code) {
        if ((int)text->t[first++].a[0] != speaker)
            return 0;
    }
    if (call) {
        if (first >= tn || text->t[first].type != T_CMD ||
            text->t[first].code != CMD_PRT || text->t[first].a[0] != call)
            return 0;
        first++;
    }
    const int last = tn - (returning ? 2 : 1);
    for (int i = first; i < last; i++) {
        const Tok *t = &text->t[i];
        if ((t->code == 0xac &&
             (i == first || (returning && text->t[i - 1].type == T_CMD))) ||
            (!GaiaPageText(t) && (t->type != T_CMD || t->code != CMD_FIN)))
            return 0;
    }

    const int before = out->n;
    if (!GaiaWrapPage(text->t + first, text->t + last, out, width, height, 1))
        return 0;
    if ((inherited && !(box && box->allow_inherited_reflow)) ||
        (returning && !(box && box->allow_phase_reflow)) || call) {
        int waits = 0;
        for (int i = before; i < out->n; i++)
            waits += out->t[i].type == T_CMD && out->t[i].code == CMD_FIN;
        if (waits != pages - 1)
            return 0;
    }
    for (int i = end; i < sn; i++)
        Push(out, &stock->t[i]);
    return 1;
}

/* A speaker change partitions the dialogue at its preceding page wait. The
 * translated source must identify the same speaker at every such boundary. */
static int GaiaSpeakerPhaseEnd(const Toks *tokens, int start, int source, int *speaker)
{
    int phase = start;
    int printed = 0;
    int at_prefix = 1;
    *speaker = -1;
    for (int i = start; i < tokens->n; ++i) {
        const Tok *t = &tokens->t[i];
        const int marker = source ? t->type == T_MARK && !t->code :
            t->type == T_CMD && t->code == 0xc2 && GaiaSpeakerTemplate(t->a[0]);
        if (marker) {
            if (!at_prefix)
                return -1;
            if (printed)
                return phase;
            if (*speaker >= 0)
                return -1;
            *speaker = (int)t->a[0];
        } else if (t->type == T_GLYPH) {
            at_prefix = 0;
            printed = 1;
        } else if (t->type == T_CMD && t->code == CMD_FIN) {
            phase = i + 1;
            at_prefix = 1;
        } else if (t->type == T_CMD && t->code == CMD_N) {
            at_prefix = 0;
        }
    }
    return tokens->n;
}

static int GaiaStockSpeakerPhases(const Toks *stock, Toks *out, const Toks *text,
                                  int measured_layout, int shared_box)
{
    Toks stock_phase = {0}, text_phase = {0};
    int start = 0, first = 0, phases = 0, ok = 0;
    GaiaBoxState box = {.allow_inherited_reflow = shared_box > 1};
    while (start < stock->n && first < text->n) {
        int stock_speaker, text_speaker;
        int stop = GaiaSpeakerPhaseEnd(stock, start, 0, &stock_speaker);
        int last = GaiaSpeakerPhaseEnd(text, first, 1, &text_speaker);
        if (stop <= start || last <= first || stock_speaker != text_speaker ||
            (stop == stock->n) != (last == text->n))
            goto done;
        const int internal = stop < stock->n;
        if (!internal && !phases)
            goto done;
        stock_phase.n = text_phase.n = 0;
        for (int i = start; i < stop; i++)
            Push(&stock_phase, &stock->t[i]);
        for (int i = first; i < last; i++)
            Push(&text_phase, &text->t[i]);
        if (internal) {
            /* A synthetic RET makes the prose pass retain the phase's final
             * FIN. For a stock END sequence with a verified shared window,
             * manual waits may be reflowed within the phase. */
            const Tok boundary = {.type = T_CMD, .code = CMD_RET, .ref = -1};
            Push(&stock_phase, &boundary);
            Push(&text_phase, &boundary);
        }
        box.allow_phase_reflow = internal && stock->t[stock->n - 1].code == CMD_END;
        if (!GaiaStockProse(&stock_phase, out, &text_phase, 0, measured_layout,
                            shared_box ? &box : NULL))
            goto done;
        if (internal)
            out->n--;
        phases++;
        start = stop;
        first = last;
    }
    ok = phases > 1 && start == stock->n && first == text->n;
done:
    free(stock_phase.t);
    free(text_phase.t);
    return ok;
}

/* D1 keeps the current bank. Include the verified plain stock suffix in
 * the same payload instead of copying a near pointer into a virtual bank. */
static int GaiaStockKnownJump(const Rom *rom, uint32_t offset,
                              Toks *stock, Toks *out, const Toks *text)
{
    const uint32_t target = 0x06bf7c;
    if (offset != 0x06be1f && offset != 0x06be85 && offset != 0x06bf0a)
        return 0;
    Tok *stock_end = &stock->t[stock->n - 1];
    const Tok *text_end = &text->t[text->n - 1];
    if (stock_end->type != T_CMD || stock_end->code != CMD_JMP ||
        stock_end->a[0] != (target & 0xffff) ||
        text_end->type != T_CMD || text_end->code != CMD_JMP ||
        text_end->a[0] != target)
        return 0;
    Toks translated = {0}, tail = {0};
    for (int i = 0; i < text->n - 1; i++)
        Push(&translated, &text->t[i]);
    const Tok boundary = {.type = T_CMD, .code = CMD_RET, .ref = -1};
    Push(&translated, &boundary);
    const Tok saved = *stock_end;
    *stock_end = boundary;
    int ok = GaiaStockSpeakerPhases(stock, out, &translated, 1, 0);
    *stock_end = saved;
    if (ok)
        ok = Decode(rom, target, &tail, 0, 0) && tail.n &&
             tail.t[tail.n - 1].code == CMD_END;
    for (int i = 0; ok && i < tail.n; i++) {
        const Tok *token = &tail.t[i];
        ok = token->type == T_GLYPH || (token->type == T_CMD &&
             (token->code == 0xc2 || token->code == 0xc3 || token->code == CMD_N ||
              token->code == CMD_FIN || token->code == CMD_END));
    }
    if (ok) {
        out->n--;  /* Remove the synthetic boundary; the stock tail ends it. */
        for (int i = 0; i < tail.n; i++)
            Push(out, &tail.t[i]);
    }
    free(translated.t);
    free(tail.t);
    return ok;
}

/* Timed cards use the stock wait immediately followed by a clear or close.
 * Reflow between those boundaries, preserving all wait arguments and the
 * open box's verified dimensions. Do not add any player-input waits. */
static int GaiaStockTimedClears(const Toks *stock, Toks *out, const Toks *text)
{
    int at = 0, source = 0, cards = 0, left = -1, top = -1;
    int width = 0, height = 0;
    while (at < stock->n && source < text->n) {
        int speaker = -1;
        while (at < stock->n && !GaiaPageText(&stock->t[at])) {
            const Tok *token = &stock->t[at];
            if (token->type != T_CMD)
                return 0;
            if (token->code == CMD_RET) {
                if (!cards || width || at != stock->n - 1 || source != text->n - 1 ||
                    text->t[source].type != T_CMD || text->t[source].code != CMD_RET)
                    return 0;
                Push(out, token);
                return 1;
            }
            if (token->code == 0xc1) {
                left = (int)token->a[0];
                top = (int)token->a[1];
                width = height = 0;
            } else if (token->code == 0xc7) {
                width = 2 * (int)token->a[0];
                height = (int)token->a[1];
                if (left < 0 || top < 1 || width < 4 || left + width >= 32 ||
                    height < 1 || top + 2 * height > 30)
                    return 0;
            } else if (token->code == 0xc2 && GaiaSpeakerTemplate(token->a[0])) {
                speaker = (int)token->a[0];
                if (speaker >= 0x12) {
                    static const uint8_t audible_speakers[] = {0, 1, 2, 4};
                    speaker = audible_speakers[speaker - 0x12];
                }
            } else if (token->code == 0xd3) {
                width = 26;
                height = 4;
            } else if (token->code != CMD_SFX && token->code != 0xd5 &&
                       token->code != 0xc3 && !(token->code == 0xce && !cards)) {
                return 0;
            }
            Push(out, token);
            at++;
        }
        if (source < text->n && text->t[source].type == T_MARK && !text->t[source].code) {
            if ((int)text->t[source].a[0] != speaker)
                return 0;
            source++;
        }
        if (!width || !height)
            return 0;
        const int first = source;
        while (source < text->n && GaiaPageText(&text->t[source]))
            source++;
        while (at < stock->n && GaiaPageText(&stock->t[at]))
            at++;
        if (source == first || at >= stock->n || source + 1 >= text->n ||
            stock->t[at].type != T_CMD || stock->t[at].code != 0xc9 ||
            text->t[source].type != T_CMD || text->t[source].code != 0xc9 ||
            stock->t[at].a[0] != text->t[source].a[0] ||
            !GaiaWrapPage(text->t + first, text->t + source, out, width, height, 0))
            return 0;
        Push(out, &stock->t[at++]);
        source++;
        if (at < stock->n && stock->t[at].type == T_CMD && stock->t[at].code == 0xc3)
            Push(out, &stock->t[at++]);
        if (at >= stock->n || stock->t[at].type != T_CMD ||
            (stock->t[at].code != 0xce && stock->t[at].code != 0xc8) ||
            text->t[source].type != T_CMD || text->t[source].code != stock->t[at].code)
            return 0;
        if (stock->t[at].code == 0xc8)
            width = height = 0;
        Push(out, &stock->t[at++]);
        source++;
        cards++;
    }
    return 0;
}

/* Keep the original window and control bytes on their exact page boundary.
 * Branching strings and controls embedded in a sentence must keep their
 * stock text. */
static int GaiaStockPageControls(const Toks *original, Toks *out, const Toks *text,
                                 int supplement)
{
    if (!original->n || original->t[original->n - 1].type != T_CMD ||
        original->t[original->n - 1].code != CMD_END)
        return 0;
    int width = 0, height = 0, speaker = -1;
    int src = 0, dst = 0;
    while (src < original->n && dst < text->n) {
        int stop = src, end = dst;
        while (stop < original->n && (original->t[stop].type != T_CMD ||
               (original->t[stop].code != CMD_FIN && original->t[stop].code != CMD_END)))
            stop++;
        while (end < text->n && (text->t[end].type != T_CMD ||
               (text->t[end].code != CMD_FIN && text->t[end].code != CMD_END)))
            end++;
        if (stop == original->n || end == text->n || original->t[stop].code != text->t[end].code)
            return 0;

        int speaker_tag = -1, prefix_pause = 0, suffix_pause = 0, palette_tag = 0;
        if (dst < end && text->t[dst].type == T_MARK && !text->t[dst].code)
            speaker_tag = (int)text->t[dst++].a[0];
        if (dst < end && text->t[dst].type == T_MARK && text->t[dst].code == 0xc9)
            prefix_pause = (int)text->t[dst++].a[0];
        int text_end = end;
        if (text_end > dst && text->t[text_end - 1].type == T_MARK &&
            text->t[text_end - 1].code == 0xc3) {
            palette_tag = 1;
            text_end--;
        }
        if (text_end > dst && text->t[text_end - 1].type == T_MARK &&
            text->t[text_end - 1].code == 0xc9)
            suffix_pause = (int)text->t[--text_end].a[0];
        if (dst == text_end)
            return 0;
        for (int i = dst; i < text_end; i++)
            if (!GaiaPageText(&text->t[i]))
                return 0;

        int new_speaker = 0, position = 0;
        while (src < stop && !GaiaPageText(&original->t[src])) {
            const Tok *t = &original->t[src++];
            switch (t->code) {
            case 0xc1:
                if (position)
                    return 0;
                position = 1;
                break;
            case 0xc2:
                if (t->a[0] >= 8 && t->a[0] <= 0x10) {
                    width = 24;
                    height = kGaiaTemplateRows[t->a[0] - 8];
                } else if (!new_speaker && GaiaSpeakerTemplate(t->a[0])) {
                    speaker = (int)t->a[0];
                    new_speaker = 1;
                } else {
                    return 0;
                }
                break;
            case 0xc7:
                width = (int)t->a[0] * 2 - 2;
                height = (int)t->a[1];
                position = 0;
                break;
            case 0xd3:
                width = 24;
                height = 4;
                break;
            case 0xc9:
                if (!prefix_pause || (int)t->a[0] != prefix_pause)
                    return 0;
                prefix_pause = 0;
                break;
            case 0xc3: case 0xc8: case 0xce: case CMD_SFX: case 0xd5:
                break;
            default:
                return 0;
            }
            Push(out, t);
        }
        const int speaker_conflict = speaker_tag >= 0 && speaker >= 0 &&
                                     speaker_tag != speaker;
        const int unmatched_speaker = (new_speaker || !supplement) &&
            (new_speaker || speaker_tag >= 0) && speaker_tag != speaker;
        if (src == stop || prefix_pause || position || speaker_conflict || unmatched_speaker)
            return 0;
        const int original_text_start = src;
        while (src < stop && GaiaPageText(&original->t[src]))
            src++;
        int page_width = width, page_height = height;
        if (!width && !height && supplement)
            GaiaInheritedPageBounds(original->t + original_text_start,
                                    original->t + src, &page_width, &page_height);
        if (page_width <= 0 || page_height <= 0)
            return 0;
        if (!GaiaFitPage(text->t + dst, text->t + text_end, out, page_width, page_height, 0) &&
            (!supplement || text->t[dst].code == 0xac ||
             !GaiaWrapPage(text->t + dst, text->t + text_end, out, page_width, page_height, 0)))
            return 0;
        for (; src < stop; src++) {
            const Tok *t = &original->t[src];
            if (t->type != T_CMD)
                return 0;
            if (t->code == 0xc9 && suffix_pause && (int)t->a[0] == suffix_pause)
                suffix_pause = 0;
            else if (t->code == 0xc3 && !t->a[0])
                palette_tag = 0;
            else
                return 0;
            Push(out, t);
        }
        if (suffix_pause || palette_tag)
            return 0;
        Push(out, &original->t[stop]);
        src = stop + 1;
        dst = end + 1;
    }
    return src == original->n && dst == text->n;
}

/* These USA choice results clear the interior of an existing box. Each
 * stock COP branch reaches the result from a known 26-column prompt without
 * closing its box. IogI18nBindStock verifies the ROM digest before import. */
static int GaiaChoiceRows(uint32_t offset)
{
    switch (offset) {
    case 0x06C136: /* Angel annex */
    case 0x088D1F: case 0x088D54: case 0x088E0F: case 0x088E72:
    case 0x088F15: case 0x088F71: case 0x08901E: case 0x089078:
    case 0x089178: case 0x089190: /* Native Village */
        return 3;
    case 0x05C1E2: case 0x05C21F: /* Freejia slave market */
    case 0x06C8DC: case 0x06C8F7: /* Angel Village */
    case 0x0796DE: case 0x07977A: case 0x079C4A: /* Watermia */
    case 0x07C860: case 0x07C8D5: /* Euro */
    case 0x08A2EC: /* Angkor Wat */
    case 0x08AEF7: case 0x08AF16: case 0x08B27F: /* Dao */
    case 0x09D2D0: /* Moon Tribe camp */
        return 4;
    default:
        return 0;
    }
}

static int GaiaStockWindow(const Rom *stock, uint32_t offset, Toks *out, const Toks *text,
                           int supplement)
{
    Toks original = {0};
    int ok = Decode(stock, offset, &original, 0, 0);
    if (!ok) {
        free(original.t);
        return 0;
    }
    if (supplement == kGaiaExtended) {
        ok = GaiaStockExactRows(&original, out, text, 0);
        if (!ok) {
            out->n = 0;
            ok = GaiaStockProse(&original, out, text, 0, 0, NULL);
        }
        free(original.t);
        return ok;
    }
    if (supplement == kGaiaStockAnchors) {
        ok = GaiaStockProse(&original, out, text, 1, 0, NULL);
        if (!ok) {
            out->n = 0;
            ok = GaiaStockSpeakerPhases(&original, out, text, 0, 0);
        }
        free(original.t);
        return ok;
    }
    if (supplement == kGaiaStockLayout) {
        if (text->t[text->n - 1].code == CMD_JMP) {
            ok = GaiaStockKnownJump(stock, offset, &original, out, text);
        } else {
            ok = GaiaStockExactRows(&original, out, text, 1);
            if (!ok) {
                out->n = 0;
                ok = GaiaStockProse(&original, out, text, 0, 1, NULL);
            }
            if (!ok) {
                out->n = 0;
                ok = GaiaStockSpeakerPhases(&original, out, text, 1, 0);
            }
            if (!ok) {
                out->n = 0;
                ok = GaiaStockTimedClears(&original, out, text);
            }
        }
        free(original.t);
        return ok;
    }
    if (supplement == kGaiaSharedBox) {
        /* A source tag can repeat the same speaker for another page. Keep
         * every original opcode and use tags only to verify speaker changes. */
        Toks normalized = {0};
        int speaker = -1;
        for (int i = 0; i < text->n; ++i) {
            const Tok *token = &text->t[i];
            if (token->type == T_MARK && !token->code) {
                if ((int)token->a[0] == speaker)
                    continue;
                speaker = (int)token->a[0];
            }
            Push(&normalized, token);
        }
        ok = GaiaStockProse(&original, out, &normalized, 0, 1, NULL);
        if (!ok) {
            out->n = 0;
            ok = GaiaStockSpeakerPhases(&original, out, &normalized, 1, 1);
        }
        free(normalized.t);
        free(original.t);
        return ok;
    }
    if (supplement == kGaiaInheritedChoice) {
        GaiaBoxState box = {26, GaiaChoiceRows(offset), 0};
        ok = box.height && original.n && original.t[0].type == T_CMD &&
             original.t[0].code == 0xce &&
             GaiaStockProse(&original, out, text, 0, 1, &box);
        free(original.t);
        return ok;
    }
    if (text->n && text->t[text->n - 1].code == CMD_RET) {
        ok = supplement && GaiaStockReturn(&original, out, text);
        free(original.t);
        return ok;
    }
    for (int i = 0; i < text->n; i++)
        if (text->t[i].type == T_MARK && text->t[i].code) {
            ok = GaiaStockPageControls(&original, out, text, supplement);
            free(original.t);
            return ok;
        }
    int prefix = 1, width = 0, height = 0, initial_speakers = 0;
    int changes_speaker = 0, other_controls = 0;
    for (int i = 0; ok && i < original.n; i++) {
        const Tok *t = &original.t[i];
        if (t->type == T_GLYPH || t->code == CMD_N || t->code == CMD_FIN) {
            prefix = 0;
        } else if (t->code == CMD_END) {
            break;
        } else if (t->code == 0xc3 || t->code == 0xce) {
            if (prefix)
                Push(out, t);
            else if (t->code != 0xc3 || i + 2 != original.n)
                other_controls = 1;
        } else if (!prefix && t->code == 0xc2 && GaiaSpeakerTemplate(t->a[0]) &&
                   i > 0 && original.t[i - 1].type == T_CMD &&
                   original.t[i - 1].code == CMD_FIN) {
            changes_speaker = 1;
        } else if (prefix && (t->code == 0xc1 || t->code == 0xc2 || t->code == 0xc7 ||
                              t->code == 0xc8 || t->code == CMD_SFX ||
                              t->code == 0xd3 || t->code == 0xd5)) {
            if (t->code == 0xc2 && t->a[0] >= 8 && t->a[0] <= 0x10) {
                width = 24;
                height = kGaiaTemplateRows[t->a[0] - 8];
            } else if (t->code == 0xc2 && !GaiaSpeakerTemplate(t->a[0])) {
                ok = 0;  /* Includes the stock route-choice prompt. */
            } else if (t->code == 0xc2) {
                initial_speakers++;
            } else if (t->code == 0xc7) {
                width = (int)t->a[0] * 2 - 2;
                height = (int)t->a[1];
            } else if (t->code == 0xd3) {
                width = 24;
                height = 4;
            }
            Push(out, t);
        } else {
            ok = 0;
        }
    }
    ok = ok && !prefix && width > 0 && height > 0 && original.n &&
        original.t[original.n - 1].code == CMD_END;
    if (changes_speaker)
        ok = ok && !other_controls && initial_speakers == (text->t[0].type == T_MARK) &&
            GaiaSpeakerSequenceMatches(&original, text);
    for (int i = 0; ok && i < text->n;) {
        if (text->t[i].type == T_MARK) {
            /* The initial stock template is already in the prefix. */
            if (changes_speaker && i) {
                Tok speaker = text->t[i];
                speaker.type = T_CMD;
                speaker.code = 0xc2;
                Push(out, &speaker);
            }
            i++;
        }
        int start = i;
        while (i + 1 < text->n &&
               (text->t[i].type != T_CMD || text->t[i].code != CMD_FIN))
            i++;
        ok = GaiaFitPage(text->t + start, text->t + i, out, width, height, !other_controls);
        if (i + 1 < text->n)
            Push(out, &text->t[i]);
        i++;
    }
    if (ok) {
        /* The original palette reset can affect neighboring dialogue. */
        if (original.n >= 2) {
            const Tok *last = &original.t[original.n - 2];
            if (last->type == T_CMD && last->code == 0xc3)
                Push(out, last);
        }
        Push(out, &text->t[text->n - 1]);
    }
    if (!ok) {
        out->n = 0;
        ok = GaiaStockPageControls(&original, out, text, supplement);
    }
    free(original.t);
    return ok;
}

/* These two stock labels expose an interior entry after setup commands only.
 * The prefix remains in ROM for the base caller, while either entry reaches
 * the same relocated body. Do not repurpose this for markers after text. */
static uint32_t GaiaMarkerTailOffset(const Rom *stock, const Label *label)
{
    static const uint8_t pause[] = {0xc9, 0x40};
    static const uint8_t templates[] = {0xc2, 0x0b, 0xc2, 0x02};
    const uint8_t *prefix;
    size_t len;
    if (!label->has_marker || label->unk16)
        return 0;
    switch (label->off) {
    case 0x049b82: prefix = pause; len = sizeof(pause); break;
    case 0x09be70: prefix = templates; len = sizeof(templates); break;
    default: return 0;
    }
    if (label->marker != len || label->off + len > stock->size ||
        memcmp(stock->rom + label->off, prefix, len))
        return 0;
    return label->off + (uint32_t)len;
}

static int GaiaStockMarkerTail(const Rom *stock, uint32_t offset, Toks *out, const Toks *text)
{
    Toks original = {0};
    int ok = Decode(stock, offset, &original, 0, 0) &&
        original.n && original.t[original.n - 1].code == CMD_END &&
        GaiaStockProse(&original, out, text, 0, 0, NULL);
    if (ok) {
        int waits = 0;
        for (int i = 0; i < original.n; i++)
            waits += original.t[i].type == T_CMD && original.t[i].code == CMD_FIN;
        for (int i = 0; i < out->n; i++)
            waits -= out->t[i].type == T_CMD && out->t[i].code == CMD_FIN;
        ok = waits == 0;
    }
    free(original.t);
    return ok;
}

static unsigned GaiaSpeakerIdentity(unsigned id)
{
    static const uint8_t spoken[] = {0, 1, 2, 4};
    return id >= 0x12 && id <= 0x15 ? spoken[id - 0x12] : id;
}

typedef struct {
    int first, prose, after_prose, last, width, height;
} GaiaManualPage;

/* Find a word split that fits all original manual pages. Keep each page's
 * stock open/clear, voice, palette and delay controls at its boundary. */
static int GaiaStockManualPages(const Toks *stock, Toks *out, const Toks *text)
{
    GaiaManualPage pages[32];
    int n_pages = 0, width = 0, height = 0, left = -1, top = -1;
    for (int i = 0; i < stock->n;) {
        if (n_pages == 32)
            return 0;
        GaiaManualPage *page = &pages[n_pages++];
        page->first = i;
        while (i < stock->n && !GaiaPageText(&stock->t[i])) {
            const Tok *token = &stock->t[i++];
            switch (token->code) {
            case 0xc1:
                left = (int)token->a[0];
                top = (int)token->a[1];
                width = height = 0;
                break;
            case 0xc2:
                if (token->a[0] >= 8 && token->a[0] <= 0x10) {
                    width = 26;
                    height = kGaiaTemplateRows[token->a[0] - 8];
                } else if (!GaiaSpeakerTemplate(token->a[0])) {
                    return 0;
                }
                break;
            case 0xc7:
                width = (int)token->a[0] * 2;
                height = (int)token->a[1];
                if (left < 1 || top < 1 || left + width > 33 || top + 2 * height > 31)
                    return 0;
                break;
            case 0xd3:
                width = 26;
                height = 4;
                break;
            case 0xc3: case 0xce: case CMD_SFX: case 0xd5:
                break;
            default:
                return 0;
            }
        }
        page->prose = i;
        while (i < stock->n && GaiaPageText(&stock->t[i]))
            ++i;
        page->after_prose = i;
        if (page->prose == i)
            return 0;
        while (i < stock->n && stock->t[i].code == 0xc3)
            ++i;
        if (i == stock->n || (stock->t[i].code != CMD_FIN && stock->t[i].code != CMD_END))
            return 0;
        page->last = ++i;
        page->width = width;
        page->height = height;
        if (!width && !height) {
            if (left >= 0 || top >= 0)
                return 0;
            GaiaInheritedPageBounds(stock->t + page->prose, stock->t + page->after_prose,
                                    &page->width, &page->height);
        }
        if (page->width < 1 || page->width > 26 || page->height < 1 || page->height > 7)
            return 0;
    }
    Toks glyphs = {0};
    int start[256], finish[256], words = 0, ok = 0;
    int gap = 1;
    for (int i = 0; i < text->n - 1; ++i) {
        const Tok *token = &text->t[i];
        if (token->type == T_MARK && !token->code)
            continue;
        if ((token->type == T_GLYPH && token->code == 0xac) ||
            (token->type == T_CMD && (token->code == CMD_N || token->code == CMD_FIN))) {
            gap = 1;
            continue;
        }
        if (token->type != T_GLYPH || glyphs.n >= 4094 || words >= 255)
            goto done;
        if (gap) {
            if (words) {
                const Tok space = {.type = T_GLYPH, .code = 0xac};
                Push(&glyphs, &space);
            }
            start[words++] = glyphs.n;
            gap = 0;
        }
        Push(&glyphs, token);
        finish[words - 1] = glyphs.n;
    }
    if (!words)
        goto done;
    uint16_t jump[32][256] = {{0}};
    for (int p = n_pages - 1; p >= 0; --p) {
        const GaiaManualPage *page = &pages[p];
        for (int begin = 0; begin < words; ++begin) {
            int rows = 1, columns = 0;
            for (int end = begin; end < words; ++end) {
                int length = finish[end] - start[end];
                if (length > page->width)
                    break;
                if (columns && columns + 1 + length > page->width) {
                    ++rows;
                    columns = 0;
                }
                if (rows > page->height)
                    break;
                columns += length + (columns != 0);
                if ((p == n_pages - 1 && end == words - 1) ||
                    (p + 1 < n_pages && jump[p + 1][end + 1]))
                    jump[p][begin] = (uint16_t)(end + 1);
            }
        }
    }
    if (!jump[0][0])
        goto done;
    int at = 0;
    for (int p = 0; p < n_pages; ++p) {
        const GaiaManualPage *page = &pages[p];
        const int next = jump[p][at];
        for (int i = page->first; i < page->prose; ++i)
            Push(out, &stock->t[i]);
        if (!GaiaWrapPage(glyphs.t + start[at], glyphs.t + finish[next - 1], out,
                          page->width, page->height, 0))
            goto done;
        for (int i = page->after_prose; i < page->last; ++i)
            Push(out, &stock->t[i]);
        at = next;
    }
    ok = 1;
done:
    free(glyphs.t);
    return ok;
}

static int GaiaManualTurnEnd(const Toks *tokens, int start, int source, int *who)
{
    int phase = start, printed = 0, prefix = 1;
    *who = -1;
    for (int i = start; i < tokens->n; ++i) {
        const Tok *token = &tokens->t[i];
        const int is_voice = source ? token->type == T_MARK && !token->code :
            token->type == T_CMD && token->code == 0xc2 && GaiaSpeakerTemplate(token->a[0]);
        if (is_voice) {
            if (!prefix)
                return -1;
            int next = (int)GaiaSpeakerIdentity(token->a[0]);
            if (printed && next != *who)
                return phase;
            *who = next;
        } else if (token->type == T_GLYPH) {
            printed = 1;
            prefix = 0;
        } else if (token->code == CMD_FIN) {
            phase = i + 1;
            prefix = 1;
        } else if (token->code == CMD_N) {
            prefix = 0;
        }
    }
    return tokens->n;
}

static int GaiaStockManualTurns(const Toks *stock, Toks *out, const Toks *text)
{
    int start = 0, first = 0;
    while (start < stock->n && first < text->n) {
        int stock_voice, authored_voice;
        const int stop = GaiaManualTurnEnd(stock, start, 0, &stock_voice);
        const int end = GaiaManualTurnEnd(text, first, 1, &authored_voice);
        if (stop <= start || end <= first || stock_voice != authored_voice ||
            (stop == stock->n) != (end == text->n))
            return 0;
        const Toks old_turn = {.t = stock->t + start, .n = stop - start};
        const Toks new_turn = {.t = text->t + first, .n = end - first};
        if (!GaiaStockManualPages(&old_turn, out, &new_turn))
            return 0;
        start = stop;
        first = end;
    }
    return start == stock->n && first == text->n;
}

/* Compare chapter prose by speaking turn, leaving stock presentation and
 * branch controls in place. Silent variants use the same palette identity.
 * Choice fragments keep their exact rows and stock cursor indentation. */
/* A complete display beat around one stock pause can reflow in its own
 * box. Keep the actual wait and every close or clear on the stock side. */
static int GaiaTimedProseSlot(const Toks *stock, Toks *out, const Toks *text)
{
    int first = 0, last, stock_pause = 0, source_pause = 0, rendered = 0, kept = 0;
    Toks model = {0}, words = {0}, laid_out = {0};
    const Tok fake_end = {.type = T_CMD, .code = CMD_END, .ref = -1};
    int ok = 0, closed = 0;
    while (first < stock->n && !GaiaPageText(&stock->t[first])) {
        const Tok *t = &stock->t[first++];
        if (t->type == T_CMD && t->code == 0xc9 && !stock_pause)
            stock_pause = -1;
        else
            Push(&model, t);
    }
    kept = model.n;
    last = first;
    while (last < stock->n && GaiaPageText(&stock->t[last]))
        Push(&model, &stock->t[last++]);
    if (last == first)
        goto done;
    for (int i = last; i < stock->n - 1; ++i) {
        const Tok *t = &stock->t[i];
        if (t->type != T_CMD)
            goto done;
        closed |= t->code == 0xc8;
        if (t->code == 0xc9 && !stock_pause)
            stock_pause = 1;
        else if (t->code != 0xc3 && t->code != 0xc8 && t->code != 0xce)
            goto done;
    }
    for (int i = 0; i < text->n - 1; ++i) {
        const Tok *t = &text->t[i];
        if (GaiaPageText(t)) {
            if (source_pause > 0)
                goto done; /* A mid-sentence pause is a separate script beat. */
            rendered |= t->type == T_GLYPH;
            Push(&words, t);
        } else if (t->type != T_GLYPH && t->code == 0xc9 && !source_pause) {
            source_pause = rendered ? 1 : -1;
        } else if ((t->type != T_GLYPH && (t->code == 0xc8 || t->code == 0xce)) ||
                   (t->type == T_MARK && !t->code)) {
            continue;
        } else {
            goto done;
        }
    }
    if (!stock_pause || stock_pause != source_pause || !rendered ||
        stock->t[stock->n - 1].code != text->t[text->n - 1].code ||
        (stock->t[stock->n - 1].code == CMD_RET && !closed))
        goto done;
    Push(&words, &fake_end);
    Push(&model, &fake_end);
    if (!GaiaStockManualPages(&model, &laid_out, &words))
        goto done;
    for (int i = 0; i < first; ++i)
        Push(out, &stock->t[i]);
    for (int i = kept; i < laid_out.n - 1; ++i)
        Push(out, &laid_out.t[i]);
    for (int i = last; i < stock->n; ++i)
        Push(out, &stock->t[i]);
    ok = 1;
done:
    free(model.t);
    free(words.t);
    free(laid_out.t);
    return ok;
}

typedef struct {
    int width, height, row, column, x, y, closed;
} GaiaBeatWindow;

static int GaiaBeatBoundary(const Tok *token)
{
    if (token->type == T_GLYPH)
        return 0;
    switch (token->code) {
    case 0xc9: case 0xd0: case CMD_FIN: case CMD_END: case CMD_RET:
        return token->code;
    default:
        return 0;
    }
}

static int GaiaBeatStockControl(GaiaBeatWindow *window, int *voice, const Tok *token)
{
    if (token->type != T_CMD)
        return 0;
    switch (token->code) {
    case 0xc1:
        window->x = (int)token->a[0];
        window->y = (int)token->a[1];
        window->width = window->height = 0;
        window->closed = 1;
        return 1;
    case 0xc2:
        if (token->a[0] >= 8 && token->a[0] <= 0x10) {
            window->width = 26;
            window->height = kGaiaTemplateRows[token->a[0] - 8];
        } else if (GaiaSpeakerTemplate(token->a[0])) {
            *voice = (int)GaiaSpeakerIdentity(token->a[0]);
            return 1;
        } else {
            return 0;
        }
        break;
    case 0xc7:
        window->width = (int)token->a[0] * 2;
        window->height = (int)token->a[1];
        if (window->x < 1 || window->y < 1 || window->x + window->width > 33 ||
            window->y + window->height * 2 > 31)
            return 0;
        break;
    case 0xd3:
        window->width = 26;
        window->height = 4;
        break;
    case 0xc8:
        window->closed = 1;
        window->width = window->height = 0;
        return 1;
    case 0xce:
        window->row = 1;
        window->column = 0;
        return 1;
    case 0xc3: case CMD_SFX: case 0xd5:
        return 1;
    default:
        return 0;
    }
    if (window->width < 1 || window->width > 26 || window->height < 1 || window->height > 7)
        return 0;
    window->closed = 0;
    window->row = 1;
    window->column = 0;
    return 1;
}

static int GaiaFitBeatWords(const Tok *at, const Tok *end, GaiaBeatWindow *window, Toks *out)
{
    if (window->closed || !window->width || !window->height)
        return 0;
    int gap = 0;
    const Tok space = {.type = T_GLYPH, .code = 0xac};
    const Tok line = {.type = T_CMD, .code = CMD_N, .ref = -1};
    while (at < end) {
        if (at->type == T_CMD && at->code == CMD_N) {
            if (++window->row > window->height)
                return 0;
            window->column = gap = 0;
            Push(out, &line);
            ++at;
            continue;
        }
        if (at->type != T_GLYPH)
            return 0;
        if (at->code == 0xac) {
            gap = 1;
            ++at;
            continue;
        }
        const Tok *stop = at + 1;
        while (stop < end && stop->type == T_GLYPH && stop->code != 0xac)
            ++stop;
        const int length = (int)(stop - at);
        if (length > window->width)
            return 0;
        if (window->column + gap + length > window->width) {
            if (++window->row > window->height)
                return 0;
            window->column = gap = 0;
            Push(out, &line);
        }
        if (gap) {
            ++window->column;
            Push(out, &space);
            gap = 0;
        }
        while (at < stop)
            Push(out, at++);
        window->column += length;
    }
    return 1;
}

/* The stock timer/input/page-stop sequence is the timeline. Track the
 * physical cursor through each beat, so a repeated wait does not reset
 * the text window or silently introduce another input prompt. */
static int GaiaCompileTimedBeats(const Toks *stock, Toks *out, const Toks *source)
{
    if (!stock->n || !source->n || stock->t[stock->n - 1].code != source->t[source->n - 1].code)
        return 0;
    GaiaBeatWindow window = {.x = -1, .y = -1, .row = 1};
    int a = 0, b = 0, voice = -1, holds = 0;
    while (a < stock->n && b < source->n) {
        int stock_end = a, source_end = b;
        while (stock_end < stock->n && !GaiaBeatBoundary(&stock->t[stock_end]))
            ++stock_end;
        if (stock_end == stock->n)
            return 0;
        const int boundary = GaiaBeatBoundary(&stock->t[stock_end]);
        holds += boundary == 0xc9 || boundary == 0xd0;
        while (a < stock_end && !GaiaPageText(&stock->t[a])) {
            if (!GaiaBeatStockControl(&window, &voice, &stock->t[a]))
                return 0;
            Push(out, &stock->t[a++]);
        }
        const int original_start = a;
        while (a < stock_end && GaiaPageText(&stock->t[a]))
            ++a;
        if (a != original_start) {
            int seen_text = 0;
            while (source_end < source->n) {
                const Tok *t = &source->t[source_end];
                if (GaiaBeatBoundary(t) || (t->type == T_CMD &&
                    (t->code == 0xc8 || t->code == 0xce))) {
                    if (seen_text || t->code == CMD_END || t->code == CMD_RET)
                        break;
                    b = source_end + 1;
                }
                if (t->type == T_MARK && !t->code &&
                    voice != (int)GaiaSpeakerIdentity(t->a[0]))
                    return 0;
                seen_text |= t->type == T_GLYPH;
                ++source_end;
            }
        }
        while (b < source_end && !GaiaPageText(&source->t[b])) {
            const Tok *tag = &source->t[b++];
            if (tag->type == T_MARK && !tag->code) {
                if (voice != (int)GaiaSpeakerIdentity(tag->a[0]))
                    return 0;
            } else if (tag->type != T_CMD || (tag->code != 0xc8 && tag->code != 0xce)) {
                return 0;
            }
        }
        const int authored_start = b;
        while (b < source_end && GaiaPageText(&source->t[b]))
            ++b;
        if ((a == original_start) != (b == authored_start))
            return 0;
        if (a > original_start && !GaiaFitBeatWords(source->t + authored_start, source->t + b, &window, out))
            return 0;
        while (a < stock_end) {
            if (!GaiaBeatStockControl(&window, &voice, &stock->t[a]))
                return 0;
            Push(out, &stock->t[a++]);
        }
        while (b < source_end) {
            const Tok *tag = &source->t[b++];
            if (tag->type != T_CMD || (tag->code != 0xc8 && tag->code != 0xce))
                return 0;
        }
        /* Do not misplace option selection rows on a returning fragment. */
        if (boundary == CMD_RET && !window.closed && window.column)
            return 0;
        Push(out, &stock->t[stock_end]);
        if (boundary == CMD_FIN) {
            window.row = 1;
            window.column = 0;
        }
        a = stock_end + 1;
        b = source_end;
    }
    for (; b < source->n - 1; ++b) {
        const Tok *token = &source->t[b];
        if (!GaiaBeatBoundary(token) && (token->type != T_CMD ||
            (token->code != 0xc8 && token->code != 0xce)))
            return 0;
    }
    return a == stock->n && b + 1 == source->n && holds > 0;
}

static int GaiaTryStockReflow(const Rom *stock, uint32_t offset, Toks *out, const Toks *text,
                              int timed)
{
    Toks original = {0}, authored = {0};
    int ok = 0, source_speaker = -1, original_speakers = 0;
    unsigned voice[8];
    for (unsigned i = 0; i < 8; ++i)
        voice[i] = i;
    if (!Decode(stock, offset, &original, 0, 0) || !original.n || !text->n)
        goto done;
    for (int i = 0; i < original.n; ++i) {
        const Tok *t = &original.t[i];
        if (t->type != T_CMD || t->code != 0xc2 || !GaiaSpeakerTemplate(t->a[0]))
            continue;
        const unsigned who = GaiaSpeakerIdentity(t->a[0]);
        if ((original_speakers & (1 << who)) && voice[who] != t->a[0])
            goto done;       /* The stock script alternates silent and voiced turns. */
        original_speakers |= 1 << who;
        voice[who] = t->a[0];
    }
    unsigned stock_controls = 0;
    for (int i = 0; timed && i < original.n; ++i) {
        const Tok *token = &original.t[i];
        if (token->type == T_CMD && token->code >= 0xc0 && token->code <= CMD_LAST)
            stock_controls |= 1u << (token->code - 0xc0);
    }
    for (int i = 0; i < text->n; ++i) {
        Tok token = text->t[i];
        /* Source-only presentation tags can disappear in stock prose. They
         * never create a new timer or change the returned state of a box. */
        if (timed && original.t[original.n - 1].code == CMD_END && token.type != T_GLYPH &&
            (token.code == 0xc9 || token.code == 0xc8 || token.code == 0xce) &&
            !(stock_controls & (1u << (token.code - 0xc0))))
            continue;
        if ((token.type == T_MARK || token.type == T_CMD) && token.code == 0xc3)
            continue;       /* The stock palette changes remain in the output. */
        if (token.type == T_MARK && !token.code) {
            unsigned who = GaiaSpeakerIdentity(token.a[0]);
            if (source_speaker == (int)who)
                continue;
            if (source_speaker >= 0 && !original_speakers)
                goto done;
            source_speaker = (int)who;
            if (!original_speakers)
                continue;
            if (!(original_speakers & (1 << who)))
                goto done;
            token.a[0] = voice[who];
        }
        Push(&authored, &token);
    }
    if (timed == 2) {
        ok = GaiaCompileTimedBeats(&original, out, &authored);
    } else if (timed && GaiaTimedProseSlot(&original, out, &authored)) {
        ok = 1;
    } else if (original.t[original.n - 1].code == CMD_RET) {
        ok = GaiaStockReturnRows(&original, out, &authored, 1);
        if (!ok) {
            out->n = 0;
            ok = GaiaStockExactRows(&original, out, &authored, 1);
        }
    } else if (original.t[original.n - 1].code == CMD_END) {
        GaiaBoxState box = {.allow_inherited_reflow = 1};
        ok = GaiaStockProse(&original, out, &authored, 0, 1, &box);
        if (!ok) {
            out->n = 0;
            ok = GaiaStockSpeakerPhases(&original, out, &authored, 1, 2);
        }
        if (!ok) {
            out->n = 0;
            for (int i = 0; i < authored.n; ++i)
                if (authored.t[i].type == T_CMD && authored.t[i].code == 0xc9)
                    authored.t[i].type = T_MARK;
            ok = GaiaStockPageControls(&original, out, &authored, 1);
        }
        if (!ok) {
            out->n = 0;
            if (!(original_speakers & (original_speakers - 1)))
                ok = GaiaStockManualPages(&original, out, &authored);
            else
                ok = GaiaStockManualTurns(&original, out, &authored);
        }
    }
done:
    free(original.t);
    free(authored.t);
    return ok;
}

/* Render into a fresh UI overlay bank only after all chapter dialogue is
 * placed. The older dialogue-only TSV and all of its pointers remain valid. */
static uint32_t GaiaUiAddress(IogPack *pack, unsigned *fill, unsigned length)
{
    if (*fill + length > kIogVirtualBankSize) {
        if (pack->nbanks >= kIogVirtualBanks)
            return 0;
        uint8_t *data = calloc(1, kIogVirtualBankSize);
        if (!data)
            return 0;
        pack->banks[pack->nbanks++] = data;
        *fill = 0;
    }
    return ((uint32_t)(kVBankFirst + pack->nbanks - 1) << 16) | (kVBase + *fill);
}

static int GaiaPatchDisjoint(const IogPack *pack, uint32_t off, unsigned len)
{
    for (int i = 0; i < pack->npatches; ++i) {
        const IogPatch *p = &pack->patches[i];
        if (p->offset < off + len && off < p->offset + p->len)
            return 0;
    }
    return 1;
}

static int GaiaTitle(const Rom *r, const Structure *st, IogPack *pack, unsigned *fill,
                     uint32_t scene_record, const char *value, unsigned width)
{
    uint32_t off = 0;
    for (int i = 0; !off && i < st->scene_n; ++i)
        if (SceneActorList(r, st, i) == scene_record)
            off = SceneTitle(r, st, i);
    if (!off)
        return 0;
    Toks original = {0};
    int ok = Decode(r, off, &original, 0, 0) && original.n &&
             original.t[original.n - 1].code == CMD_RET;
    for (int i = 0; ok && i + 1 < original.n; ++i)
        ok = original.t[i].type == T_GLYPH;
    free(original.t);
    if (!ok)
        return 0;
    /* The stock call centers within the supplied width using an unsigned cursor. */
    uint8_t encoded[27];
    if (width >= sizeof(encoded))
        return 0;
    unsigned n = 0;
    while (*value && n < width) {
        if (*value == '[' || !GlyphFor(&value, &encoded[n]) || encoded[n] >= CMD_END)
            return 0;
        ++n;
    }
    if (!n || *value)
        return 0;
    encoded[n] = CMD_RET;
    unsigned span = SceneTitleLen(r, off) + 1;
    if (width == 18 && n + 1 <= span && GaiaPatchDisjoint(pack, off, n + 1)) {
        if (memcmp(r->rom + off, encoded, n + 1))
            AddPatch(pack, off, encoded, n + 1);
        return 1;
    }
    if (span < 7 || !GaiaPatchDisjoint(pack, off, 7))
        return 0;
    /* The wider box moves four cells left. Compensate by decreasing the
     * advertised width by eight, so the stock (18-width)/2 cursor moves
     * four cells right. Both execution tiers keep the same stock code. */
    const int measured = (int)n - ((int)width - 18);
    for (int i = 0; i < 3; ++i) {
        const uint32_t addr = GaiaUiAddress(pack, fill, n + 1);
        if (!addr)
            return 0;
        if (AddSceneRedirectWidth(pack, r, off, addr, measured)) {
            memcpy(pack->banks[pack->nbanks - 1] + *fill, encoded, n + 1);
            *fill += n + 1;
            return 1;
        }
        ++*fill;
    }
    return 0;
}

/* Extend verified dictionary B by one pointer, moving its first word into
 * the bank's unused tail without changing the word selected by index zero.
 * The three-byte Mu slot can then address the full title as a dictionary
 * word. Neither the title code nor the actor lists need relocation. */
static int GaiaShortTitle(const Rom *stock, const Structure *st, IogPack *pack, const char *value)
{
    enum { Record = 0x0ca71b, Title = 0x0ca7ea, Dictionary = 0x01f54d, FirstWord = 0x01f6dd,
           Padding = 0x01ff6c, NewIndex = 0xc8 };
    const uint8_t first_word[] = {0x21, 0x29, 0x29, 0x24, 0xac, CMD_RET};
    const uint8_t short_title[] = {0x4c, 0xa5, CMD_RET};
    if (stock->size < Title + sizeof(short_title) || SceneActorList(stock, st, 0x5f) != Record ||
        SceneTitle(stock, st, 0x5f) != Title || memcmp(stock->rom + Title, short_title, sizeof(short_title)) ||
        Dictionary + 2 * NewIndex != FirstWord || Rd16(stock, Dictionary) != (FirstWord & 0xffff) ||
        memcmp(stock->rom + FirstWord, first_word, sizeof(first_word)) ||
        !GaiaPatchDisjoint(pack, Dictionary, 2) || !GaiaPatchDisjoint(pack, FirstWord, 2) ||
        !GaiaPatchDisjoint(pack, Title, sizeof(short_title)))
        return 0;
    uint8_t text[16];
    unsigned len = 0;
    while (*value && len < sizeof(text) - 1) {
        if (*value == '[' || !GlyphFor(&value, &text[len]) || text[len] >= CMD_END)
            return 0;
        ++len;
    }
    if (len != sizeof(text) - 1 || *value)
        return 0;
    text[len++] = CMD_RET;
    uint8_t data[sizeof(first_word) + 2 + sizeof(text)];
    if (!GaiaPatchDisjoint(pack, Padding, sizeof(data)))
        return 0;
    for (unsigned i = 0; i < sizeof(data); ++i)
        if (stock->rom[Padding + i] != 0xff)
            return 0;
    memcpy(data, first_word, sizeof(first_word));
    /* The title counter sees 17 dictionary bytes. The renderer advances six
     * tile words before the actual 15 glyphs, centering them in the wide box. */
    data[sizeof(first_word)] = 0xcc;
    data[sizeof(first_word) + 1] = 12;
    memcpy(data + sizeof(first_word) + 2, text, len);
    const uint32_t title_start = Padding + sizeof(first_word);
    const uint8_t old_pointer[] = {(uint8_t)Padding, (uint8_t)(Padding >> 8)};
    const uint8_t new_pointer[] = {(uint8_t)title_start, (uint8_t)(title_start >> 8)};
    const uint8_t title[] = {CMD_LU2, NewIndex, CMD_RET};
    AddPatch(pack, Padding, data, sizeof(data));
    AddPatch(pack, Dictionary, old_pointer, sizeof(old_pointer));
    AddPatch(pack, FirstWord, new_pointer, sizeof(new_pointer));
    AddPatch(pack, Title, title, sizeof(title));
    return 1;
}

static void GaiaWideTitles(FILE *file, const Rom *stock, const Structure *structure, IogPack *pack)
{
    enum { Format = 0x02a169, Width = 26 };
    const uint8_t format[] = {0xc1, 7, 7, 0xc7, 10, 1, 0xd2, 0, CMD_RET};
    if (stock->size < Format + sizeof(format) || memcmp(stock->rom + Format, format, sizeof(format)) ||
        !GaiaPatchDisjoint(pack, Format, sizeof(format)) || fseek(file, 0, SEEK_SET))
        return;

    unsigned fill = kIogVirtualBankSize, installed = 0;
    char line[4096];
    while (fgets(line, sizeof(line), file)) {
        if (strncmp(line, "scene_", 6))
            continue;
        char *value = strchr(line, '\t');
        if (!value)
            continue;
        *value++ = 0;
        value[strcspn(value, "\r\n")] = 0;
        const uint32_t record = (uint32_t)strtoul(line + 6, NULL, 16);
        if (strlen(value) > 18)
            installed += GaiaTitle(stock, structure, pack, &fill, record, value, Width);
        else if (record == 0x0ca71b)
            installed += GaiaShortTitle(stock, structure, pack, value);
    }
    if (installed) {
        const uint8_t box[] = {0xc1, 3, 7, 0xc7, 14, 1, 0xd2, 0, CMD_RET};
        AddPatch(pack, Format, box, sizeof(box));
        pack->scene_translated += installed;
    }
}

static uint8_t GaiaMenuGlyph(unsigned c)
{
    if (c >= 'A' && c <= 'Z') return (uint8_t)c;
    if (c >= 'a' && c <= 'z') return (uint8_t)c;
    if (c >= '0' && c <= '9') return (uint8_t)c;
    switch (c) {
    case ' ': return 0x60;
    case '.': return 0x20;
    case '!': return 0x21;
    case '*': return 0x2a;
    case ',': return 0x2c;
    case '+': return 0x2d;
    case '-': return 0x2e;
    case '/': return 0x2f;
    case ':': return 0x3a;
    case '(': return 0x3c;
    case ')': return 0x3e;
    case '?': return 0x3f;
    case '\'': return 0x5c;
    case '"': return 0x82;
    default: return 0;
    }
}

/* Menu rows can be shared by multiple callers. Preserve their row advances
 * and never exceed the stock text's width on any line. */
static unsigned GaiaMenuText(const Toks *original, const char *text, uint8_t encoded[128],
                             int description)
{
    unsigned n = 0, column = 0, shared_width = 0;
    if (description) {
        /* DBL returns to the same left gutter on every description row. */
        for (int i = 0; i < original->n; ++i) {
            const Tok *token = &original->t[i];
            if (token->type == T_GLYPH) {
                if (++column > shared_width)
                    shared_width = column;
            } else if (token->code == 0x0d) {
                column = 0;
            } else {
                return 0;
            }
        }
        column = 0;
    }
    for (int i = 0; i <= original->n;) {
        unsigned limit = 0;
        while (i < original->n && original->t[i].type == T_GLYPH) {
            ++i;
            ++limit;
        }
        if (description && limit)
            limit = shared_width;
        while (*text && *text != '[') {
            const uint8_t glyph = GaiaMenuGlyph((unsigned char)*text++);
            if (!glyph || ++column > limit || n >= 127)
                return 0;
            encoded[n++] = glyph;
        }
        if (i == original->n) {
            if (*text || (!n && i))
                return 0;
            encoded[n++] = 0;
            return n;
        }
        const unsigned command = original->t[i++].code;
        if (command == 0x11 && !strncmp(text, "[N]", 3))
            text += 3;
        else if (command == 0x0d && !strncmp(text, "[DBL]", 5))
            text += 5;
        else
            return 0;
        if (n >= 127)
            return 0;
        encoded[n++] = (uint8_t)command;
        column = 0;
    }
    return 0;
}

static int GaiaMenu(const AsciiRom *ascii, const Structure *st, IogPack *pack,
                    unsigned *fill, uint32_t off, const char *text, int description)
{
    if (AsciiIndex(st, off) < 0 || !ascii->engine)
        return 0;
    Toks original = {0};
    uint8_t encoded[128];
    unsigned length = 0;
    uint32_t span = 0;
    if (AsciiDecodeSpan(ascii, off, &original, 0, &span)) {
        length = GaiaMenuText(&original, text, encoded, 0);
        if (description)
            length = length ? 0 : GaiaMenuText(&original, text, encoded, 1);
    }
    free(original.t);
    if (!length)
        return 0;
    const Rom *r = &ascii->rom;
    /* The checked stock console labels bound each slot. */
    uint32_t next = (uint32_t)r->size;
    for (int i = 0; i < st->nascii; ++i)
        if (st->ascii[i] > off && st->ascii[i] < next)
            next = st->ascii[i];
    for (int i = 0; i < st->nptab; ++i)
        if (st->ptab[i] > off && st->ptab[i] < next)
            next = st->ptab[i];
    if (span > next - off)
        return 0;
    if (length <= span && GaiaPatchDisjoint(pack, off, length)) {
        if (memcmp(r->rom + off, encoded, length))
            AddPatch(pack, off, encoded, length);
        return 1;
    }
    if (span < 5 || !GaiaPatchDisjoint(pack, off, 5))
        return 0;
    uint32_t addr = GaiaUiAddress(pack, fill, length);
    if (!addr)
        return 0;
    AddRedirect(pack, off, A_PRT, addr, 0);
    memcpy(pack->banks[pack->nbanks - 1] + *fill, encoded, length);
    *fill += length;
    return 1;
}

/* The named lookups in the source are its optional JP/EN switch. The
 * Original integration uses the EN entries of those seven pinned tables. */
static const char *GaiaMenuName(const char *tag, size_t len)
{
    static const struct { const char *table, *name; } names[] = {
        {"will", "Will"}, {"lola", "Lola"}, {"lance", "Lance"}, {"friar", "Friar"},
        {"freedan", "Freedan"}, {"rama", "Rama"}, {"lilly", "Lilly"},
    };
    const char prefix[] = "[TBL:@item_name_table_";
    const char suffix[] = ",B24]";
    if (len <= sizeof(prefix) + sizeof(suffix) - 2 || memcmp(tag, prefix, sizeof(prefix) - 1) ||
        memcmp(tag + len - (sizeof(suffix) - 1), suffix, sizeof(suffix) - 1))
        return NULL;
    const size_t key_len = len - sizeof(prefix) - sizeof(suffix) + 2;
    for (size_t i = 0; i < sizeof(names) / sizeof(*names); ++i)
        if (strlen(names[i].table) == key_len && !memcmp(tag + sizeof(prefix) - 1, names[i].table, key_len))
            return names[i].name;
    return NULL;
}

static unsigned GaiaMenuExtendedText(const AsciiRom *ascii, const char *text, uint8_t *encoded,
                                      unsigned width, unsigned rows, uint8_t newline)
{
    unsigned n = 0, columns = 0, line = 1;
    if (newline == 0x0d) {
        if (strncmp(text, "[DBL]", 5))
            return 0;  /* description starts below the item name */
        encoded[n++] = newline;
        text += 5;
    }
    while (*text) {
        if (n >= 126)
            return 0;
        if (*text != '[') {
            const uint8_t c = GaiaMenuGlyph((unsigned char)*text++);
            if (!c || ++columns > width)
                return 0;
            encoded[n++] = c;
            continue;
        }
        const char *end = strchr(text, ']');
        if (!end)
            return 0;
        const size_t len = (size_t)(end + 1 - text);
        if ((newline == 0x11 && len == 3 && !memcmp(text, "[N]", len)) ||
            (newline == 0x0d && len == 5 && !memcmp(text, "[DBL]", len))) {
            if (++line > rows)
                return 0;
            columns = 0;
            encoded[n++] = newline;
        } else if (len == 6 && !memcmp(text, "[LU:", 4) && strchr("247C", text[4])) {
            const unsigned index = text[4] == 'C' ? 12 : (unsigned)(text[4] - '0');
            const uint32_t word = (ascii->lu & 0xff0000) | Rd16(&ascii->rom, ascii->lu + 2 * index);
            Toks tokens = {0};
            int ok = AsciiDecode(ascii, word, &tokens, 0) && columns + tokens.n <= width && n + tokens.n < 127;
            for (int i = 0; ok && i < tokens.n; ++i)
                ok = tokens.t[i].type == T_GLYPH;
            if (ok) {
                for (int i = 0; i < tokens.n; ++i)
                    encoded[n++] = tokens.t[i].code;
                columns += tokens.n;
            }
            free(tokens.t);
            if (!ok)
                return 0;
        } else {
            const char *name = GaiaMenuName(text, len);
            if (!name || columns + strlen(name) > width || n + strlen(name) >= 127)
                return 0;
            for (; *name; ++name, ++columns)
                encoded[n++] = GaiaMenuGlyph((unsigned char)*name);
        }
        text = end + 1;
    }
    if (!n || !columns)
        return 0;
    encoded[n++] = 0;
    return n;
}

static int GaiaMenuLate(const AsciiRom *ascii, const Structure *st, IogPack *pack,
                        unsigned *fill, uint32_t off, const char *text)
{
    if (AsciiIndex(st, off) < 0 || !ascii->engine)
        return 0;
    unsigned width, rows;
    uint8_t newline;
    if (off >= 0x01db3f && off < 0x01de1e) {
        width = 10; rows = 2; newline = 0x11;  /* status item column */
    } else if (off >= 0x01de9e && off < 0x01e12a) {
        width = 19; rows = 1; newline = 0;     /* item description heading */
    } else if (off >= 0x01e184 && off < 0x01e5ec) {
        width = 19; rows = 3; newline = 0x0d;
    } else if (off == 0x01e61f || off == 0x01e697 || off == 0x01e7d6 || off == 0x01e7dd) {
        width = 11; rows = 2; newline = 0x11;  /* Dark Power and character names */
    } else {
        return 0;
    }

    Toks original = {0};
    uint32_t span;
    uint8_t encoded[128];
    int ok = AsciiDecodeSpan(ascii, off, &original, 0, &span);
    if (ok && (GaiaMenuText(&original, text, encoded, 0) ||
               (newline == 0x0d && GaiaMenuText(&original, text, encoded, 1))))
        ok = 0;  /* old page and address are already installed */
    for (int i = 0; ok && i < original.n; ++i)
        ok = original.t[i].type == T_GLYPH || original.t[i].code == newline;
    free(original.t);
    if (!ok)
        return 0;

    const unsigned length = GaiaMenuExtendedText(ascii, text, encoded, width, rows, newline);
    if (!length)
        return 0;
    const unsigned stub = length <= span ? length : 5;
    if (stub > span || !GaiaPatchDisjoint(pack, off, stub))
        return 0;
    for (int i = 0; i < st->nascii; ++i)
        if (st->ascii[i] > off && st->ascii[i] < off + span)
            return 0;
    for (int i = 0; i < st->nptab; ++i)
        if (st->ptab[i] > off && st->ptab[i] < off + span)
            return 0;
    if (length <= span) {
        if (memcmp(ascii->rom.rom + off, encoded, length))
            AddPatch(pack, off, encoded, length);
    } else {
        const uint32_t addr = GaiaUiAddress(pack, fill, length);
        if (!addr)
            return 0;
        AddRedirect(pack, off, A_PRT, addr, 0);
        memcpy(pack->banks[pack->nbanks - 1] + *fill, encoded, length);
        *fill += length;
    }
    return 1;
}

static void GaiaLateMenu(FILE *file, const AsciiRom *ascii, const Structure *structure, IogPack *pack)
{
    if (fseek(file, 0, SEEK_SET))
        return;
    unsigned fill = kIogVirtualBankSize;
    char line[4096];
    while (fgets(line, sizeof(line), file)) {
        if (strncmp(line, "menu_", 5))
            continue;
        char *value = strchr(line, '\t');
        if (!value)
            continue;
        *value++ = 0;
        value[strcspn(value, "\r\n")] = 0;
        pack->menu_translated += GaiaMenuLate(ascii, structure, pack, &fill, (uint32_t)strtoul(line + 5, NULL, 16), value);
    }
}

enum { kGaiaMenu = 1, kGaiaScene, kGaiaSprite, kGaiaPrologue, kGaiaMapNames = 64 };

typedef struct {
    uint32_t off;
    char text[32];
} GaiaMapName;

static int GaiaSpriteGlyph(char ch)
{
    static const char glyphs[] = "ABCDEFGHIJKLMNO!PQRSTUVWXYZ/?-()"
                                 "abcdefghijklmno pqrstuvwxyz,.'\"";
    const char *glyph = strchr(glyphs, ch);
    if (!glyph || !ch)
        return -1;
    unsigned i = (unsigned)(glyph - glyphs);
    return (int)((i & 7) + 16 * (i / 8));
}

static unsigned GaiaSpriteText(const char *text, uint8_t encoded[32])
{
    unsigned n = 0;
    for (; *text && n < 31; ++text) {
        int glyph = GaiaSpriteGlyph(*text);
        if (glyph < 0)
            return 0;
        encoded[n++] = (uint8_t)glyph;
    }
    if (*text || !n)
        return 0;
    encoded[n++] = CMD_RET;
    return n;
}

static void GaiaMapSprites(const Rom *r, const Structure *st, IogPack *pack,
                           const GaiaMapName *names, unsigned count)
{
    if (!count || !st->map_table || st->map_table >= st->map_start ||
        st->map_start >= st->map_end || st->map_end > r->size ||
        (st->map_start >> 16) != ((st->map_end - 1) >> 16) ||
        !GaiaPatchDisjoint(pack, st->map_table, st->map_end - st->map_table))
        return;
    const unsigned capacity = st->map_end - st->map_start;
    if (capacity > 0x4000)
        return;
    uint8_t *region = malloc(capacity);
    if (!region)
        return;
    unsigned position[kGaiaMapNames], size[kGaiaMapNames], used = 0, n = 0, applied = 0;
    uint8_t table[3 * kGaiaMapNames];
    uint32_t site = st->map_table;
    while (site < st->map_start && r->rom[site]) {
        if (site + 3 > st->map_start || n >= kGaiaMapNames)
            goto done;
        const uint32_t off = (st->map_table & 0xff0000) | Rd16(r, site + 1);
        if (off < st->map_start || off >= st->map_end)
            goto done;
        const uint8_t *bytes = r->rom + off;
        unsigned length = SpriteLen(r, off);
        if (!length || off + length > st->map_end)
            goto done;
        uint8_t translated[32];
        for (unsigned i = 0; i < count; ++i) {
            if (names[i].off != off)
                continue;
            const unsigned len = GaiaSpriteText(names[i].text, translated);
            if (len) {
                int seen = 0;
                for (uint32_t prior = st->map_table; prior < site; prior += 3)
                    seen |= Rd16(r, prior + 1) == (off & 0xffff);
                applied += !seen;
                bytes = translated;
                length = len;
            }
            break;
        }
        unsigned at = used;
        for (unsigned i = 0; i < n; ++i)
            if (size[i] == length && !memcmp(region + position[i], bytes, length)) {
                at = position[i];
                break;
            }
        if (at == used) {
            if (used + length > capacity)
                goto done;
            memcpy(region + used, bytes, length);
            used += length;
        }
        position[n] = at;
        size[n] = length;
        at += st->map_start;
        table[3 * n] = r->rom[site];
        table[3 * n + 1] = (uint8_t)at;
        table[3 * n + 2] = (uint8_t)(at >> 8);
        ++n;
        site += 3;
    }
    if (applied && site < st->map_start && !r->rom[site]) {
        AddPatch(pack, st->map_table, table, n * 3);
        AddPatch(pack, st->map_start, region, used);
        pack->sprite_translated += applied;
    }
done:
    free(region);
}

static int GaiaUiLabel(const char *label)
{
    if (!strncmp(label, "menu_", 5)) return kGaiaMenu;
    if (!strncmp(label, "scene_", 6)) return kGaiaScene;
    if (!strncmp(label, "sprite_", 7)) return kGaiaSprite;
    if (!strncmp(label, "prologue_", 9)) return kGaiaPrologue;
    return 0;
}

static int GaiaPrologueCard(const Rom *r, const Structure *st, IogPack *pack,
                            uint32_t *next, uint32_t offset, const char *text)
{
    static const uint8_t spawn[] = {0x02, 0xa0, 0x8f, 0xcf, 0x8b};
    static const uint8_t store[] = {0x99, 0x26, 0x00};
    uint32_t site = 0;
    for (int i = 0; i < st->npro && !site; ++i)
        if (st->pro_str[i] == offset)
            site = st->pro_site[i];
    if (site < 12 || site + 5 > r->size || r->rom[site - 1] != 0xa9 ||
        (site >> 16) != (st->free_start >> 16) ||
        ((st->free_end - 1) >> 16) != (site >> 16) ||
        (site & 0xff0000u) + Rd16(r, site) != offset ||
        memcmp(r->rom + site - 12, spawn, sizeof(spawn)) ||
        memcmp(r->rom + site + 2, store, sizeof(store)))
        return 0;
    const unsigned x = Rd16(r, site - 7), y = Rd16(r, site - 5);
    uint8_t bytes[128];
    unsigned n = 0, width = 0, row = y, sprites = 0;
    while (*text && n < sizeof(bytes) - 1) {
        if (!strncmp(text, "[N]", 3)) {
            bytes[n++] = CMD_N;
            row += 16;
            width = 0;
            text += 3;
        } else {
            const int glyph = GaiaSpriteGlyph(*text++);
            if (glyph < 0 || x + 8 * ++width > 256)
                return 0;
            sprites += glyph != 0x57;
            bytes[n++] = (uint8_t)glyph;
        }
    }
    if (*text || !n || row + 16 > 224 || sprites > 96 ||
        *next < st->free_start || st->free_end > r->size ||
        *next + n + 1 > st->free_end || !GaiaPatchDisjoint(pack, site, 2) ||
        !GaiaPatchDisjoint(pack, *next, n + 1))
        return 0;
    bytes[n++] = CMD_RET;
    for (unsigned i = 0; i < n; ++i)
        if (r->rom[*next + i] != 0xff)
            return 0;
    const uint8_t imm[] = {(uint8_t)*next, (uint8_t)(*next >> 8)};
    AddPatch(pack, *next, bytes, n);
    AddPatch(pack, site, imm, 2);
    *next += n;
    return 1;
}

/* Relocate both entrances together. The marker follows a stock page wait,
 * and a caller entering at the marker renders only the verified suffix. */
static int GaiaPairedEntry(const Rom *stock, const Structure *structure, int li,
                           IogPack *pack, unsigned *fill, char *source, int reflow)
{
    const Label *label = &structure->l[li];
    const uint32_t entry = label->off, marker = entry + label->marker;
    char *separator = strchr(source, '|');
    if (!separator || strchr(separator + 1, '|') || !label->has_marker || label->unk16 ||
        label->marker < 5 || marker >= stock->size ||
        stock->rom[marker - 1] != CMD_FIN || StringSpan(stock, marker) < 5 ||
        !GaiaPatchDisjoint(pack, entry, 5) || !GaiaPatchDisjoint(pack, marker, 5))
        return 0;
    for (int i = 0; i < structure->nl; ++i) {
        if (i == li)
            continue;
        const Label *other = &structure->l[i];
        uint32_t ref = other->off;
        uint32_t inner = ref + other->marker;
        if (ref - entry < 5 || ref - marker < 5 || (other->has_marker &&
            (inner - entry < 5 || inner - marker < 5)))
            return 0;
    }
    *separator++ = 0;
    Toks prefix = {0}, suffix = {0}, original = {0};
    Item base = {0}, tail = {0};
    int ok = 0;
    if (!GaiaDialogue(source, &prefix) || !GaiaDialogue(separator, &suffix) ||
        !Decode(stock, entry, &original, 0, 0))
        goto done;
    int split = 0;
    while (split < original.n && original.t[split].src < marker)
        ++split;
    if (!split || split >= original.n || original.t[split].src != marker ||
        original.t[split - 1].code != CMD_FIN)
        goto done;
    Toks borrowed_tail = {.t = original.t + split, .n = original.n - split};
    if (!GaiaStockProse(&borrowed_tail, &tail.toks, &suffix, 0, 1, NULL)) {
        tail.toks.n = 0;
        if (!GaiaStockSpeakerPhases(&borrowed_tail, &tail.toks, &suffix, 1, 1)) {
            tail.toks.n = 0;
            if (!GaiaStockReturn(&borrowed_tail, &tail.toks, &suffix)) {
                tail.toks.n = 0;
                if (!reflow || !GaiaTryStockReflow(stock, marker, &tail.toks, &suffix, 0))
                    goto done;
            }
        }
    }
    original.n = split;
    const Tok boundary = {.type = T_CMD, .code = CMD_RET, .ref = -1};
    Push(&original, &boundary);
    if (!GaiaStockProse(&original, &base.toks, &prefix, 0, 1, NULL)) {
        base.toks.n = 0;
        if (!GaiaStockSpeakerPhases(&original, &base.toks, &prefix, 1, 1)) {
            if (!reflow || prefix.n < 2 || prefix.t[prefix.n - 2].code != CMD_FIN)
                goto done;
            --original.n;
            --prefix.n;
            base.toks.n = 0;
            if (!GaiaStockManualTurns(&original, &base.toks, &prefix))
                goto done;
        }
    }
    /* Place the real tail over the synthetic RET, immediately after FIN. */
    unsigned first = (unsigned)Encode(NULL, &base, NULL) - 1;
    unsigned last = (unsigned)Encode(NULL, &tail, NULL);
    if (!first || !last || first + last > kIogVirtualBankSize)
        goto done;
    uint32_t addr = GaiaUiAddress(pack, fill, first + last);
    if (!addr)
        goto done;
    uint8_t *data = pack->banks[pack->nbanks - 1] + *fill;
    Encode(NULL, &base, data);
    Encode(NULL, &tail, data + first);
    AddRedirect(pack, entry, CMD_PRT, addr, CMD_RET);
    AddRedirect(pack, marker, CMD_PRT, addr + first, CMD_RET);
    *fill += first + last;
    ok = 1;
done:
    free(prefix.t);
    free(suffix.t);
    free(original.t);
    free(base.toks.t);
    free(tail.toks.t);
    return ok;
}

/* Run after interface allocation as well as the previous chapter passes.
 * A save can still hold any of their exact virtual pointers. */
static void GaiaLateBeatDialogue(FILE *file, const Rom *stock, const Structure *structure,
                                 IogPack *pack)
{
    if (fseek(file, 0, SEEK_SET))
        return;
    unsigned fill = kIogVirtualBankSize;
    char line[4096];
    while (fgets(line, sizeof(line), file)) {
        if (strncmp(line, "widestring_", 11))
            continue;
        char *text = strchr(line, '\t');
        if (!text)
            continue;
        *text++ = 0;
        text[strcspn(text, "\r\n")] = 0;
        if (!strncmp(text, "[LAY]", 5))
            text += 5;
        if (!strncmp(text, "[PAIR]", 6) || !strncmp(text, "[TAIL]", 6))
            continue;
        const int li = FindLabel(structure, line);
        if (li < 0)
            continue;
        const Label *label = &structure->l[li];
        const uint32_t off = label->off;
        if (label->has_marker || label->unk16 || !GaiaPatchDisjoint(pack, off, 5) ||
            StringSpan(stock, off) < 5)
            continue;
        int disjoint = 1;
        for (int i = 0; disjoint && i < structure->nl; ++i) {
            if (i == li)
                continue;
            const Label *next = &structure->l[i];
            disjoint = next->off - off >= 5 &&
                (!next->has_marker || next->off + next->marker - off >= 5);
        }
        if (!disjoint)
            continue;
        Toks parsed = {0};
        Item item = {0};
        if (GaiaDialogue(text, &parsed) && GaiaTryStockReflow(stock, off, &item.toks, &parsed, 2)) {
            const unsigned length = (unsigned)Encode(NULL, &item, NULL);
            const uint32_t address = GaiaUiAddress(pack, &fill, length);
            if (address) {
                Encode(NULL, &item, pack->banks[pack->nbanks - 1] + fill);
                AddRedirect(pack, off, CMD_PRT, address, CMD_RET);
                fill += length;
                ++pack->strings_translated;
            }
        }
        free(parsed.t);
        free(item.toks.t);
    }
}

#include "iog_static_chapter.inc"

IogPack *IogTextBuildGaiaPack(const uint8_t *usa, size_t usa_size,
                             const char *structure_path, const char *dialogue_path)
{
    Rom stock;
    if (!RomInit(&stock, usa, usa_size))
        return NULL;
    FILE *file = fopen(dialogue_path, "rb");
    if (!file)
        return NULL;
    Structure structure;
    if (!LoadStructure(&structure, structure_path)) {
        fclose(file);
        return NULL;
    }
    IogPack *pack = calloc(1, sizeof(*pack));
    if (!pack) {
        fclose(file);
        free(structure.l);
        free(structure.t);
        free(structure.ascii);
        return NULL;
    }
    snprintf(pack->code, sizeof(pack->code), "gaia");
    snprintf(pack->name, sizeof(pack->name), "GaiaLabs Retranslation");
    unsigned fill = 0, paired_fill = kIogVirtualBankSize, reflow_fill = kIogVirtualBankSize;
    unsigned timed_fill = kIogVirtualBankSize;
    unsigned ui_fill = kIogVirtualBankSize;
    AsciiRom ascii = {0};
    GaiaMapName names[kGaiaMapNames];
    unsigned n_names = 0;
    uint32_t prologue_next = structure.free_start;
    char line[4096];
    int malformed = 0;
    /* Append supplemental entries only after the original overlay layout.
     * Save states can hold an active dialogue pointer into those banks. */
    for (int supplement = kGaiaBase; supplement <= kGaiaTimedReflow && !malformed; supplement++) {
        uint32_t last = 0;
        int ui_kind = 0;
        uint32_t ui_last = 0;
        while (fgets(line, sizeof(line), file)) {
            size_t size = strlen(line);
            if (!size || line[size - 1] != '\n') {
                malformed = 1;
                break;
            }
            line[--size] = 0;
            if (size && line[size - 1] == '\r')
                line[size - 1] = 0;
            char *text = strchr(line, '\t');
            if (!text) {
                malformed = 1;
                break;
            }
            *text++ = 0;
            const int kind = GaiaUiLabel(line);
            if (kind) {
                const char *hex = line + (kind == kGaiaPrologue ? 9 : 4 + kind);
                unsigned off = 0;
                if (strlen(hex) != 6 || strspn(hex, "0123456789ABCDEF") != 6 ||
                    sscanf(hex, "%x", &off) != 1 || off >= stock.size ||
                    kind < ui_kind || (kind == ui_kind && off <= ui_last)) {
                    malformed = 1;
                    break;
                }
                ui_kind = kind;
                ui_last = off;
                if (kind == kGaiaPrologue && supplement == kGaiaPairedEntry) {
                    pack->sprite_translated += GaiaPrologueCard(&stock, &structure, pack,
                                                                &prologue_next, off, text);
                    continue;
                }
                if (kind == kGaiaMenu && supplement == kGaiaPairedEntry &&
                    off >= 0x01e184 && off < 0x01e5ec) {
                    pack->menu_translated += GaiaMenu(&ascii, &structure, pack, &paired_fill,
                                                      off, text, 1);
                    continue;
                }
                if (supplement != kGaiaInheritedChoice || kind == kGaiaPrologue)
                    continue;
                if (kind == kGaiaMenu) {
                    if (!pack->menu_total++ && !AsciiInit(&ascii, &stock))
                        ascii.engine = 0;
                    pack->menu_translated += GaiaMenu(&ascii, &structure, pack, &ui_fill, off, text, 0);
                } else if (kind == kGaiaScene) {
                    ++pack->scene_total;
                    pack->scene_translated += GaiaTitle(&stock, &structure, pack, &ui_fill, off, text, 18);
                } else if (n_names < kGaiaMapNames && strlen(text) < sizeof(names[0].text)) {
                    names[n_names].off = off;
                    strcpy(names[n_names++].text, text);
                }
                continue;
            }
            int li = FindLabel(&structure, line);
            if (ui_kind || li < 0 || strncmp(line, "widestring_", 11) ||
                structure.l[li].off <= last) {
                malformed = 1;
                break;
            }
            const Label *label = &structure.l[li];
            last = label->off;
            pack->strings_total += !supplement;
            if (!strncmp(text, "[PAIR]", 6)) {
                if (supplement == kGaiaPairedEntry)
                    pack->strings_translated += GaiaPairedEntry(&stock, &structure, li, pack,
                                                              &paired_fill, text + 6, 0);
                else if (supplement == kGaiaStockReflow)
                    pack->strings_translated += GaiaPairedEntry(&stock, &structure, li, pack,
                                                              &reflow_fill, text + 6, 1);
                continue;
            }
            if (supplement == kGaiaPairedEntry)
                continue;
            const int layout_only = !strncmp(text, "[LAY][EXT]", 10);
            if (layout_only) {
                if (supplement < kGaiaStockLayout)
                    continue;
                text += 5;
            }
            const int tail = !strncmp(text, "[TAIL][EXT]", 11);
            if (tail) {
                if (supplement != kGaiaStockAnchors)
                    continue;
                text += 6;
            }
            const int extended = !strncmp(text, "[EXT]", 5);
            if (extended && supplement < kGaiaExtended)
                continue;
            Toks tokens = {0};
            if (!GaiaDialogue(text, &tokens)) {
                free(tokens.t);
                malformed = 1;
                break;
            }
            const uint32_t patch_at = tail ? GaiaMarkerTailOffset(&stock, label) : label->off;
            uint32_t span = patch_at ? StringSpan(&stock, patch_at) : 0;
            int safe = !label->unk16 && (tail || !label->has_marker) && span >= 5;
            for (int i = 0; safe && i < structure.nl; i++) {
                const Label *entry = &structure.l[i];
                if (i != li && entry->off >= patch_at && entry->off - patch_at < 5)
                    safe = 0;
                if (tail && i != li && entry->has_marker &&
                    entry->off + entry->marker >= patch_at &&
                    entry->off + entry->marker - patch_at < 5)
                    safe = 0;
            }
            for (int i = 0; safe && tail && i < pack->npatches; i++) {
                const IogPatch *prev = &pack->patches[i];
                if (prev->offset < patch_at + 5 && prev->offset + prev->len > patch_at)
                    safe = 0;
            }
            Item item = {0};
            int accepted = 0;
            if (safe && supplement >= kGaiaStockReflow) {
                accepted = GaiaPatchDisjoint(pack, patch_at, 5) &&
                           GaiaTryStockReflow(&stock, patch_at, &item.toks, &tokens,
                                              supplement == kGaiaTimedReflow);
            } else if (safe && tail) {
                accepted = GaiaStockMarkerTail(&stock, patch_at, &item.toks, &tokens);
            } else if (safe) {
                int first = layout_only ? kGaiaStockLayout :
                            extended ? kGaiaExtended : kGaiaBase;
                for (int stage = first; stage <= supplement; stage++) {
                    item.toks.n = 0;
                    if (GaiaStockWindow(&stock, label->off, &item.toks, &tokens, stage)) {
                        accepted = stage == supplement;
                        break;
                    }
                }
            }
            if (accepted) {
                unsigned *placement = &fill;
                if (supplement == kGaiaStockReflow)
                    placement = &reflow_fill;
                else if (supplement == kGaiaTimedReflow)
                    placement = &timed_fill;
                unsigned len = (unsigned)Encode(NULL, &item, NULL);
                if (!pack->nbanks || *placement + len > kIogVirtualBankSize) {
                    if (pack->nbanks == kIogVirtualBanks || len > kIogVirtualBankSize) {
                        free(item.toks.t);
                        free(tokens.t);
                        malformed = 1;
                        break;
                    }
                    uint8_t *bank_data = calloc(1, kIogVirtualBankSize);
                    if (!bank_data) {
                        free(item.toks.t);
                        free(tokens.t);
                        malformed = 1;
                        break;
                    }
                    pack->banks[pack->nbanks++] = bank_data;
                    *placement = 0;
                }
                unsigned bank = (unsigned)pack->nbanks - 1;
                Encode(NULL, &item, pack->banks[bank] + *placement);
                AddRedirect(pack, patch_at, CMD_PRT, ((kVBankFirst + bank) << 16) | (kVBase + *placement), CMD_RET);
                *placement += len;
                pack->strings_translated++;
            }
            free(item.toks.t);
            free(tokens.t);
        }
        malformed |= ferror(file);
        if (supplement < kGaiaTimedReflow && !malformed && fseek(file, 0, SEEK_SET))
            malformed = 1;
    }
    if (!malformed) {
        GaiaWideTitles(file, &stock, &structure, pack);
        GaiaLateMenu(file, &ascii, &structure, pack);
        GaiaLateBeatDialogue(file, &stock, &structure, pack);
        GaiaApplyStaticChapter(file, &stock, &structure, pack);
    }
    fclose(file);
    if (!malformed)
        GaiaMapSprites(&stock, &structure, pack, names, n_names);
    free(structure.l);
    free(structure.t);
    free(structure.ascii);
    if (malformed || !pack->npatches) {
        IogTextFreePack(pack);
        return NULL;
    }
    return pack;
}

/* The runs of text of a string, '|'-separated (for the report). */
static void RunsText(const Toks *v, char *out, size_t cap)
{
    size_t n = 0;
    int in = 0;
    out[0] = 0;
    for (int k = 0; k < v->n && n + 8 < cap; k++) {
        if (v->t[k].type == T_GLYPH) {
            if (!in && n) out[n++] = '|';
            in = 1;
            const char *g = GlyphText(v->t[k].code);
            while (*g && n + 1 < cap) out[n++] = *g++;
        } else if (v->t[k].type == T_CMD) {
            in = 0;
        }
    }
    out[n] = 0;
}

typedef struct { const char *label, *lang, *text; } HandText;
static const HandText kHand[] = {
#include "iog_hand_text.inc"
};

/* Replace the runs of v with the hand translation of `label` in `lang`. */
static int ApplyHand(const char *label, const char *lang, Toks *v)
{
    const char *text = NULL;
    for (size_t i = 0; i < sizeof(kHand) / sizeof(kHand[0]); i++)
        if (!strcmp(kHand[i].label, label) && !strcmp(kHand[i].lang, lang))
            text = kHand[i].text;
    if (!text)
        return 0;
    int runs = 0, parts = 1;
    for (int k = 0, in = 0; k < v->n; k++) {
        if (v->t[k].type == T_GLYPH) { if (!in) runs++; in = 1; }
        else if (v->t[k].type == T_CMD) in = 0;
    }
    for (const char *p = text; *p; p++) parts += *p == '|';
    if (runs != parts) {
        fprintf(stderr, "[i18n] hand text %s/%s: %d parts for %d runs\n", label, lang, parts, runs);
        return 0;
    }
    Toks nv = {0};
    const char *p = text;
    for (int k = 0; k < v->n;) {
        if (v->t[k].type != T_GLYPH) { Push(&nv, &v->t[k]); k++; continue; }
        Tok tpl = v->t[k];
        while (k < v->n && v->t[k].type == T_GLYPH) k++;
        while (*p && *p != '|') {
            uint8_t c;
            if (GlyphFor(&p, &c)) { tpl.code = c; Push(&nv, &tpl); }
        }
        if (*p == '|') p++;
    }
    free(v->t);
    *v = nv;
    return 1;
}

static IogPack *Assemble(const Structure *stp, const Rom *rup, Text *usa_text, const int *usa_ok,
                         Toks *tr, const int *has, int adopt, const char *code, const char *name)
{
    Structure st = *stp;
    Rom ru = *rup;
    const uint8_t *usa = ru.rom;
    size_t usa_size = ru.size;
    /* Final token list of every label: the translation, else the USA text. */
    Item *items = calloc((size_t)st.nl, sizeof(Item));
    int *item_of = malloc((size_t)st.nl * sizeof(int));
    int nitems = 0, translated = 0;
    for (int li = 0; li < st.nl; li++) {
        item_of[li] = -1;
        if (!usa_ok[li])
            continue;
        Item *it = &items[nitems];
        it->li = li;
        it->relocatable = 1;
        if (has[li] && (!adopt || AdoptUsaStructure(&usa_text[li].toks, &tr[li]))) {
            it->toks = tr[li];
            tr[li].t = NULL;
            translated++;
        } else {
            it->toks = usa_text[li].toks;
            usa_text[li].toks.t = NULL;
            if (ApplyHand(st.l[li].name, code, &it->toks)) {
                translated++;
            } else if (getenv("IOG_I18N_REPORT")) {
                int glyphs = 0;
                for (int k = 0; k < it->toks.n; k++)
                    glyphs += it->toks.t[k].type == T_GLYPH;
                if (glyphs > 1) {
                    char runs[1024];
                    RunsText(&it->toks, runs, sizeof(runs));
                    fprintf(stderr, "[i18n] untranslated %s (%s, %d glyphs): %s\n", st.l[li].name,
                            has[li] ? "structure differs" : "no pair", glyphs, runs);
                }
            }
        }
        if (st.l[li].unk16) {
            /* Strip the text's own [RET]; the raw tail follows it in ROM. */
            Toks *v = &it->toks;
            if (v->n && v->t[v->n - 1].type == T_CMD && v->t[v->n - 1].code == CMD_RET)
                v->n--;
            uint32_t p = st.l[li].off;
            Toks tmp = {0};
            Decode(&ru, p, &tmp, 0, 0);
            /* tail: 4 bytes after the USA string's [RET] */
            uint32_t end = p;
            while (end < usa_size && usa[end] != CMD_RET)
                end++;
            memcpy(it->tail, usa + end + 1, 4);
            free(tmp.t);
        }
        item_of[li] = nitems++;
    }

    /* Placement: strings of one USA bank (and its tables) share a virtual
     * bank; iterate until every bank-relative reference resolves. */
    IogPack *pack = calloc(1, sizeof(IogPack));
    snprintf(pack->code, sizeof(pack->code), "%s", code);
    snprintf(pack->name, sizeof(pack->name), "%s", name);
    int *table_bank = malloc((size_t)(st.nt ? st.nt : 1) * sizeof(int));
    int *table_pos = malloc((size_t)(st.nt ? st.nt : 1) * sizeof(int));
    Layout lay = {items, nitems, item_of, table_bank, table_pos, &st};
    uint8_t *scratch = malloc(0x8000);
    for (int pass = 0; pass < 8; pass++) {
        int fill[kIogVirtualBanks] = {0};
        for (int k = 0; k < st.nt; k++)
            table_bank[k] = -1;
        for (int i = 0; i < nitems; i++)
            items[i].placed = 0;
        for (uint32_t bank = 0; bank < 0x40; bank++) {
            int need = 0;
            for (int i = 0; i < nitems; i++)
                if (items[i].relocatable && (st.l[items[i].li].off >> 16) == bank) {
                    int n = Encode(NULL, &items[i], NULL);
                    items[i].len = n + (st.l[items[i].li].unk16 ? 4 : 0);
                    need += items[i].len;
                }
            for (int k = 0; k < st.nt; k++)
                if ((st.t[k].off >> 16) == bank)
                    need += 2 * st.t[k].n;
            if (!need)
                continue;
            int vb = 0;
            while (vb < kIogVirtualBanks && fill[vb] + need > kIogVirtualBankSize)
                vb++;
            if (vb == kIogVirtualBanks)
                break;
            for (int i = 0; i < nitems; i++)
                if (items[i].relocatable && (st.l[items[i].li].off >> 16) == bank) {
                    items[i].bank_index = vb;
                    items[i].pos = fill[vb];
                    items[i].placed = 1;
                    fill[vb] += items[i].len;
                }
            for (int k = 0; k < st.nt; k++)
                if ((st.t[k].off >> 16) == bank) {
                    table_bank[k] = vb;
                    table_pos[k] = fill[vb];
                    fill[vb] += 2 * st.t[k].n;
                }
        }
        int dropped = 0;
        for (int i = 0; i < nitems; i++)
            if (items[i].placed && Encode(&lay, &items[i], scratch) < 0) {
                items[i].relocatable = 0;
                dropped++;
            }
        if (!dropped) {
            for (int vb = 0; vb < kIogVirtualBanks; vb++)
                if (fill[vb])
                    pack->nbanks = vb + 1;
            break;
        }
    }
    for (int vb = 0; vb < pack->nbanks; vb++)
        pack->banks[vb] = calloc(1, kIogVirtualBankSize);
    for (int i = 0; i < nitems; i++)
        if (items[i].placed)
            Encode(&lay, &items[i], pack->banks[items[i].bank_index] + items[i].pos);
    for (int k = 0; k < st.nt; k++) {
        if (table_bank[k] < 0)
            continue;
        uint8_t *t = pack->banks[table_bank[k]] + table_pos[k];
        for (int e = 0; e < st.t[k].n; e++) {
            int li = st.t[k].entry[e];
            int ii = li >= 0 ? item_of[li] : -1;
            uint32_t v = 0;
            if (ii >= 0 && items[ii].placed && items[ii].bank_index == table_bank[k])
                v = kVBase + (uint32_t)items[ii].pos +
                    (st.t[k].entry_m[e] ? (uint32_t)MarkerPos(&items[ii]) : 0);
            else if (li >= 0)
                v = (st.l[li].off + (st.t[k].entry_m[e] ? st.l[li].marker : 0)) & 0xFFFF;
            t[2 * e] = (uint8_t)v;
            t[2 * e + 1] = (uint8_t)(v >> 8);
        }
    }

    /* Redirects: [PRT:@virtual][RET] over each relocated dialogue string
     * with room for it before the next string. */
    for (int i = 0; i < nitems; i++) {
        const Label *l = &st.l[items[i].li];
        if (!items[i].placed || l->unk16)
            continue;
        uint32_t next = l->off + 0x10000;
        for (int j = 0; j < st.nl; j++)
            if (st.l[j].off > l->off && st.l[j].off < next)
                next = st.l[j].off;
        if (next - l->off < 5)
            continue;
        /* ...and within the string itself (code may follow it). */
        if (StringSpan(&ru, l->off) < 5)
            continue;
        uint32_t addr = ((uint32_t)(kVBankFirst + items[i].bank_index) << 16) | (kVBase + (uint32_t)items[i].pos);
        if (l->scene) {
            AddSceneRedirect(pack, &ru, l->off, addr, &items[i].toks);
            continue;
        }
        AddRedirect(pack, l->off, CMD_PRT, addr, CMD_RET);
    }
    pack->strings_translated = translated;
    pack->strings_total = nitems;

    for (int i = 0; i < nitems; i++)
        free(items[i].toks.t);
    free(items); free(item_of); free(table_bank); free(table_pos); free(scratch);
    return pack;
}

IogPack *IogTextBuildPack(const uint8_t *usa, size_t usa_size, const uint8_t *eu,
                          size_t eu_size, const char *structure_path)
{
    const char *lang = IogTextRomLanguage(eu, eu_size);
    Structure st;
    Rom ru, re;
    if (!lang || !LoadStructure(&st, structure_path) || !RomInit(&ru, usa, usa_size) ||
        !RomInit(&re, eu, eu_size)) {
        fprintf(stderr, "[i18n] cannot build a pack (%s)\n",
                !lang ? "not an Illusion of Time ROM" : "structure or text engine not found");
        return NULL;
    }

    int *scene_map = malloc(4096 * sizeof(int));
    for (int i = 0; i < 4096; i++)
        scene_map[i] = -1;
    AddSceneLabels(&st, &ru, scene_map);

    /* USA text of every label, references resolved. */
    Text *usa_text = calloc((size_t)st.nl, sizeof(Text));
    int *usa_ok = calloc((size_t)st.nl, sizeof(int));
    for (int i = 0; i < st.nl; i++) {
        if (Decode(&ru, st.l[i].off, &usa_text[i].toks, 0, 0))
            usa_ok[i] = ResolveUsa(&st, i, &usa_text[i].toks);
        usa_text[i].nskel = Skeleton(&usa_text[i].toks, usa_text[i].skel, 64);
    }

    /* Call sites. */
    enum { kMaxSites = 16384 };
    Site *us = calloc(kMaxSites, sizeof(Site)), *es = calloc(kMaxSites, sizeof(Site));
    /* USA: LDY sites are tried against every bank; only a pointer that names
     * exactly one known string is kept. */
    uint8_t all_banks[0x40], ldy_banks[0x40];
    int nldy = 0;
    for (int b = 0; b < 0x40; b++)
        all_banks[b] = (uint8_t)b;
    int nus_all = Sites(usa, usa_size, us, kMaxSites, all_banks, 0x40), nus = 0;
    for (int i = 0; i < nus_all; i++) {
        int m = -1, count = 0;
        for (int j = 0; j < st.nl; j++)
            if (st.l[j].off == us[i].target && !st.l[j].unk16)
                m = j, count++;
        if (us[i].op == 0xA0) {
            /* the same LDY appears once per bank tried: keep it only if
             * its pointer is unambiguous across banks */
            int total = 0;
            for (int j = 0; j < st.nl; j++)
                total += !st.l[j].unk16 && (st.l[j].off & 0xFFFF) == (us[i].target & 0xFFFF);
            if (total != 1)
                m = -1;
        }
        if (m >= 0 && count == 1) {
            us[nus] = us[i];
            us[nus++].li = m;
            if (us[i].op == 0xA0) {
                uint8_t b = (uint8_t)(us[i].target >> 16);
                int seen = 0;
                for (int k = 0; k < nldy; k++)
                    seen |= ldy_banks[k] == b;
                if (!seen)
                    ldy_banks[nldy++] = b;
            }
        }
    }
    int nes_all = Sites(eu, eu_size, es, kMaxSites, ldy_banks, nldy), nes = 0;
    Text *eu_text = calloc((size_t)nes_all, sizeof(Text));
    for (int i = 0; i < nes_all; i++) {
        Text t = {0};
        if (!Decode(&re, es[i].target, &t.toks, 0, 0)) {
            free(t.toks.t);
            continue;
        }
        t.nskel = Skeleton(&t.toks, t.skel, 64);
        eu_text[nes] = t;
        es[nes] = es[i];
        es[nes].li = nes;
        nes++;
    }

    /* Banded monotonic alignment. */
    const int band = 250;
    int *best = calloc((size_t)(nus + 1) * (size_t)(nes + 1), sizeof(int));
    uint8_t *move = calloc((size_t)(nus + 1) * (size_t)(nes + 1), 1);
#define B(i, j) best[(size_t)(i) * (size_t)(nes + 1) + (size_t)(j)]
#define M(i, j) move[(size_t)(i) * (size_t)(nes + 1) + (size_t)(j)]
    for (int i = 1; i <= nus; i++) {
        int centre = nes ? (int)((long)i * nes / nus) : 0;
        for (int j = 1; j <= nes; j++) {
            int v = B(i - 1, j), mv = 1;
            if (B(i, j - 1) > v)
                v = B(i, j - 1), mv = 2;
            if (j >= centre - band && j <= centre + band) {
                int sc = Score(&ru, &us[i - 1], &usa_text[us[i - 1].li], &re, &es[j - 1],
                               &eu_text[j - 1]);
                if (sc >= 0 && B(i - 1, j - 1) + sc > v)
                    v = B(i - 1, j - 1) + sc, mv = 3;
            }
            B(i, j) = v;
            M(i, j) = (uint8_t)mv;
        }
    }
    Toks *tr = calloc((size_t)st.nl, sizeof(Toks));   /* translated tokens */
    int *has = calloc((size_t)st.nl, sizeof(int));
    for (int i = nus, j = nes; i && j;) {
        int mv = M(i, j);
        if (mv == 3) {
            int li = us[i - 1].li;
            if (!has[li]) {
                Toks c = {0};
                for (int k = 0; k < eu_text[j - 1].toks.n; k++)
                    Push(&c, &eu_text[j - 1].toks.t[k]);
                tr[li] = c;
                has[li] = 1;
            }
            i--, j--;
        } else if (mv == 1) {
            i--;
        } else {
            j--;
        }
    }
#undef B
#undef M
    free(best);
    free(move);

    /* Follow references in step: a USA reference and the European one in the
     * same position name the same string (or table). */
    for (int changed = 1; changed;) {
        changed = 0;
        for (int li = 0; li < st.nl; li++) {
            if (!has[li] || !usa_ok[li])
                continue;
            uint32_t bank = st.l[li].off & 0xFF0000;
            const Toks *u = &usa_text[li].toks;
            const Toks *e = &tr[li];
            int ku = 0;
            for (int i = 0; i < e->n; i++) {
                const Tok *et = &e->t[i];
                if (et->type != T_CMD || !IsRef(et->code) || et->ref >= 0)
                    continue;
                const Tok *ut = NULL;
                for (int j = 0, seen = 0; j < u->n; j++)
                    if (u->t[j].type == T_CMD && IsRef(u->t[j].code) && seen++ == ku) {
                        ut = &u->t[j];
                        break;
                    }
                ku++;
                if (!ut || ut->code != et->code || ut->ref < 0 || ut->ref_m)
                    continue;
                int targets[256], nt = 0;
                uint32_t eoffs[256];
                if (et->code == CMD_ADR) {
                    const Table *t = &st.t[ut->ref];
                    uint32_t etab = bank | et->a[0];
                    for (int k = 0; k < t->n && nt < 256; k++)
                        if (t->entry[k] >= 0 && !t->entry_m[k]) {
                            targets[nt] = t->entry[k];
                            eoffs[nt++] = bank | Rd16(&re, etab + 2 * (uint32_t)k);
                        }
                } else {
                    targets[0] = ut->ref;
                    eoffs[0] = et->code == CMD_JMP ? (bank | et->a[0])
                                                   : ((et->a[0] & 0x3F0000) | (et->a[0] & 0xFFFF));
                    nt = 1;
                }
                for (int k = 0; k < nt; k++) {
                    int tl = targets[k];
                    if (tl < 0 || has[tl])
                        continue;
                    Toks c = {0};
                    if (!Decode(&re, eoffs[k], &c, 0, 0) || (st.l[tl].unk16 && c.n == 0)) {
                        free(c.t);
                        continue;
                    }
                    if (st.l[tl].unk16 && c.n && c.t[c.n - 1].type == T_CMD &&
                        c.t[c.n - 1].code == CMD_RET)
                        c.n--;
                    tr[tl] = c;
                    has[tl] = 1;
                    changed = 1;
                }
            }
        }
    }

    /* Scene titles: paired by map index. */
    for (int li = 0; li < st.nl; li++) {
        if (scene_map[li] < 0 || has[li])
            continue;
        uint32_t off = SceneTitle(&re, &st, scene_map[li]);
        Toks c = {0};
        if (off && SceneTitleLen(&re, off) && Decode(&re, off, &c, 0, 0)) {
            tr[li] = c;
            has[li] = 1;
        } else {
            free(c.t);
        }
    }
    free(scene_map);

    IogPack *pack = Assemble(&st, &ru, usa_text, usa_ok, tr, has, 1, lang, LanguageName(lang));
    AddFont(&st, &ru, &re, pack);
    AddAscii(&st, &ru, &re, pack);
    AddSprites(&st, &ru, &re, pack);
    for (int i = 0; i < st.nl; i++) {
        free(usa_text[i].toks.t);
        free(tr[i].t);
    }
    for (int i = 0; i < nes; i++)
        free(eu_text[i].toks.t);
    free(usa_text); free(usa_ok); free(us); free(es); free(eu_text); free(tr); free(has);
    free(st.l); free(st.t); free(st.ascii);
    return pack;
}

