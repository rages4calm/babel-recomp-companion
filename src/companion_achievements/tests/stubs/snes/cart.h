/* Test stub for audit_test.c only: the fields audit.c reads. */
#pragma once
#include <stdint.h>
#define CART_HIROM 2
typedef struct Cart { uint8_t *rom; uint32_t romSize; int type; uint32_t romImageSize; } Cart;
