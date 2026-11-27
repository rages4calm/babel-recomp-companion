/* Test stub for audit_test.c only: the fields audit.c reads. */
#pragma once
#include <stdint.h>
#include "snes/cart.h"
typedef struct Snes { Cart *cart; uint8_t *ram; } Snes;
