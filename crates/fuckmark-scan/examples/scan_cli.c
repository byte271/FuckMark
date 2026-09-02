#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fuckmark_scan.h"

static void print_packed_json(uint8_t *ptr) {
    uint32_t length = (uint32_t)ptr[0]
        | ((uint32_t)ptr[1] << 8)
        | ((uint32_t)ptr[2] << 16)
        | ((uint32_t)ptr[3] << 24);
    fwrite(ptr + 4, 1, length, stdout);
    fputc('\n', stdout);
    fm_dealloc(ptr, 4 + length);
}

int main(int argc, char **argv) {
    const char *text = argc > 1 ? argv[1] : "a\xE2\x80\xAE" "b";
    const char *language = argc > 2 ? argv[2] : "auto";
    const char *categories = "*";
    uint8_t *result = fm_scan(
        (const uint8_t *)text,
        (uint32_t)strlen(text),
        (const uint8_t *)language,
        (uint32_t)strlen(language),
        (const uint8_t *)categories,
        (uint32_t)strlen(categories),
        -1
    );
    if (result == NULL) {
        fprintf(stderr, "fm_scan failed\n");
        return 1;
    }
    print_packed_json(result);
    return 0;
}
