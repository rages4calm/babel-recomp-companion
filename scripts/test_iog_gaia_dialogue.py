#!/usr/bin/env python3
"""Check stock-window Gaia dialogue handling with ROM-free synthetic messages."""
import argparse
from pathlib import Path
import subprocess

from import_gaialabs_dialogue import convert

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
#include "iog_text.c"

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "%s\n", #expr); exit(1); } } while (0)

static int CountToken(const Toks *tokens, uint8_t type, uint8_t code, unsigned argument)
{
    int count = 0;
    for (int i = 0; i < tokens->n; i++) {
        const Tok *token = &tokens->t[i];
        count += token->type == type && token->code == code && token->a[0] == argument;
    }
    return count;
}

static void CheckWindow(const uint8_t *data, size_t size, const char *text,
                        int accepted, int pages, int will, int kara)
{
    Rom stock = {.rom = data, .size = size};
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue(text, &parsed));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed) == accepted);
    if (accepted) {
        CHECK(CountToken(&rendered, T_CMD, CMD_FIN, 0) == pages - 1);
        CHECK(CountToken(&rendered, T_CMD, 0xc2, 0) == will);
        CHECK(CountToken(&rendered, T_CMD, 0xc2, 1) == kara);
        CHECK(rendered.t[rendered.n - 1].code == CMD_END);
    }
    free(parsed.t);
    free(rendered.t);
}

static void RejectMalformed(const char *text)
{
    Toks tokens = {0};
    CHECK(!GaiaDialogue(text, &tokens));
    free(tokens.t);
}

static void CheckStockSound(void)
{
    const uint8_t leading[] = {0xc2, 9, CMD_SFX, 0x10, 0x40, CMD_END};
    const uint8_t midpage[] = {0xc2, 9, 0x40, CMD_SFX, 0x10, 0x41, CMD_END};
    const uint8_t next_page[] = {0xc2, 9, 0x40, CMD_FIN, CMD_SFX, 0x10, 0x41, CMD_END};
    Rom stock = {.rom = leading, .size = sizeof(leading)};
    Toks parsed = {0}, rendered = {0};
    CHECK(GaiaDialogue("A[END]", &parsed));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed));
    CHECK(rendered.n == 4 && rendered.t[1].code == CMD_SFX && rendered.t[1].a[0] == 0x10);
    free(parsed.t);
    free(rendered.t);
    CheckWindow(midpage, sizeof(midpage), "A[END]", 0, 0, 0, 0);
    stock = (Rom){.rom = next_page, .size = sizeof(next_page)};
    parsed = (Toks){0};
    rendered = (Toks){0};
    CHECK(GaiaDialogue("A[FIN]B[END]", &parsed));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed));
    CHECK(rendered.n == 6 && rendered.t[2].code == CMD_FIN);
    CHECK(rendered.t[3].code == CMD_SFX && rendered.t[3].a[0] == 0x10);
    free(parsed.t);
    free(rendered.t);
    CheckWindow(next_page, sizeof(next_page), "A B[END]", 0, 0, 0, 0);
    RejectMalformed("[SFX:10]A[END]");
}

static void CheckPageControls(void)
{
    const uint8_t pauses[] = {0xc9, 0x1e, 0xc2, 9, 0x40, CMD_FIN,
        0xc1, 3, 17, 0xc7, 13, 3, 0xce, 0xd5, 1, 0x41, 0xc9, 0x28, 0xc3, 0, CMD_END};
    const uint8_t no_reset[] = {0xd3, 0x40, CMD_END};
    const uint8_t mid_pause[] = {0xd3, 0x40, 0xc9, 0x1e, 0x41, CMD_END};
    Rom stock = {.rom = pauses, .size = sizeof(pauses)};
    Toks parsed = {0}, rendered = {0};
    const char *verified = "[PAU:1E]A[FIN]B[PAU:28][PAL:00][END]";
    CHECK(GaiaDialogue(verified, &parsed));
    CHECK(GaiaStockWindow(&stock, 0, &rendered, &parsed));
    Item item = {.toks = rendered};
    uint8_t encoded[sizeof(pauses)] = {0};
    CHECK(Encode(NULL, &item, NULL) == sizeof(pauses));
    Encode(NULL, &item, encoded);
    CHECK(!memcmp(encoded, pauses, sizeof(pauses)));
    free(parsed.t);
    free(rendered.t);
    CheckWindow(pauses, sizeof(pauses), "[PAU:28]A[FIN]B[PAU:1E][PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(pauses, sizeof(pauses), "[PAU:1E]A[FIN]B[PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(pauses, sizeof(pauses), "[PAU:1E]A B[PAU:28][PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(no_reset, sizeof(no_reset), "A[PAL:00][END]", 0, 0, 0, 0);
    CheckWindow(mid_pause, sizeof(mid_pause), "A B[PAU:1E][END]", 0, 0, 0, 0);
    RejectMalformed("A[PAU:1E]B[END]");
    RejectMalformed("A[PAU:00][END]");
    RejectMalformed("A[PAL:04][END]");
}

int main(void)
{
    const uint8_t plain[] = {0xc2, 9, 0x40, CMD_END};
    const uint8_t changed[] = {0xc2, 9, 0xc2, 0, 0x40, CMD_FIN,
                               0xc2, 1, 0x41, 0xc3, 0, CMD_END};
    const uint8_t moving_box[] = {0xc2, 9, 0x40, CMD_FIN, 0xc2, 8, 0x41, CMD_END};
    const uint8_t mid_speaker[] = {0xc2, 9, 0x40, 0xc2, 1, 0x41, CMD_END};
    const uint8_t extra_clear[] = {0xc2, 9, 0x40, 0xce, 0x41, CMD_END};
    const uint8_t inherited[] = {0xce, 0x40, CMD_END};
    CheckWindow(plain, sizeof(plain), "A[N]B[N]C[END]", 1, 1, 0, 0);
    CheckWindow(plain, sizeof(plain),
                "For longer text[N]wrap the words[N]across a second page[END]", 1, 2, 0, 0);
    CheckWindow(plain, sizeof(plain), "[TPL:01]A[END]", 1, 1, 0, 0);
    CheckWindow(changed, sizeof(changed), "[TPL:00]A[N]B[N]C[FIN][TPL:01]D[END]", 1, 2, 1, 1);
    CheckWindow(changed, sizeof(changed), "[TPL:00]A[FIN][TPL:02]B[END]", 0, 0, 0, 0);
    CheckWindow(changed, sizeof(changed), "A[FIN]B[END]", 0, 0, 0, 0);
    CheckWindow(moving_box, sizeof(moving_box), "A[FIN]B[END]", 1, 2, 0, 0);
    CheckWindow(moving_box, sizeof(moving_box), "A[FIN]B[N]C[END]", 0, 0, 0, 0);
    CheckWindow(mid_speaker, sizeof(mid_speaker), "A[FIN][TPL:01]B[END]", 0, 0, 0, 0);
    CheckWindow(extra_clear, sizeof(extra_clear), "A[N]B[N]C[END]", 0, 0, 0, 0);
    CheckWindow(inherited, sizeof(inherited), "A[END]", 0, 0, 0, 0);
    RejectMalformed("[TPL:11]A[END]");
    RejectMalformed("A[TPL:01]B[END]");
    RejectMalformed("[TPL:+1]A[END]");
    RejectMalformed("[TPL:01][TPL:01]A[END]");
    CheckStockSound();
    CheckPageControls();
    puts("Passed Gaia stock-window and speaker checks");
    return 0;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="clang")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / ".local").resolve()):
        parser.error("--out must be within the project's .local directory")
    out.mkdir(parents=True, exist_ok=False)
    assert convert("[TPL:A][TPL:0]A[N]B[N]C[N]D[FIN][TPL:1]E[END]", []) == (
        "[TPL:00]A[N]B[N]C[FIN]D[FIN][TPL:01]E[END]"
    )
    assert convert("[PAU:1E][DLG:3,11][SIZ:D,3]A[FIN]B[PAU:28][PAL:0][END]", []) == (
        "[PAU:1E]A[FIN]B[PAU:28][PAL:00][END]"
    )
    for invalid in (
        "[SIZ:D,3]A[END]", "[DLG:3,11]A[END]", "[DLG:1F,11][SIZ:D,3]A[END]",
        "A[PAU:1E]B[END]", "A[PAL:0]B[END]", "A[PAL:0][FIN]B[END]",
    ):
        try:
            convert(invalid, [])
        except ValueError:
            continue
        raise AssertionError(f"Accepted malformed dialogue {invalid!r}")
    source = out / "test.c"
    source.write_text(HARNESS, encoding="ascii")
    binary = out / "test.exe"
    subprocess.run([args.compiler, "-std=c11", "-I", str(ROOT / "src"),
                    str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
