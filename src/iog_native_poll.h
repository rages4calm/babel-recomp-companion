#ifndef IOG_NATIVE_POLL_H
#define IOG_NATIVE_POLL_H

#include "snes/interp816.h"

/* Compiled effects for the two stock RDNMI polling instructions. Event
 * admission, bus timing and retirement remain owned by the bridge. */
int IogNativePollStep(Interp816 *in);
void IogNativePollInitialize(void);

#endif
