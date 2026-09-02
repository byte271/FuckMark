#ifndef FUCKMARK_SCAN_H
#define FUCKMARK_SCAN_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

uint8_t *fm_alloc(uint32_t size);
void fm_dealloc(uint8_t *ptr, uint32_t size);
int32_t fm_classify(uint32_t codepoint);

uint8_t *fm_scan(
    const uint8_t *text_ptr,
    uint32_t text_len,
    const uint8_t *lang_ptr,
    uint32_t lang_len,
    const uint8_t *cats_ptr,
    uint32_t cats_len,
    int32_t max_findings
);

uint8_t *fm_clean(
    const uint8_t *text_ptr,
    uint32_t text_len,
    const uint8_t *cats_ptr,
    uint32_t cats_len
);

#ifdef __cplusplus
}
#endif

#endif
