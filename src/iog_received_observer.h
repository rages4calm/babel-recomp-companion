#ifndef IOG_RECEIVED_OBSERVER_H
#define IOG_RECEIVED_OBSERVER_H
#include <stdbool.h>
#include "iog_visual_objects.h"
bool IogReceivedObserverPicture(IogVisualReceivedSource *out);
void IogReceivedObserverInitialize(void);
void IogReceivedObserverFrame(void);
void IogReceivedObserverBeforeNmi(void);
void IogReceivedObserverAfterNmi(void);
void IogReceivedObserverReset(void);
#endif
