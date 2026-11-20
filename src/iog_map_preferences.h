#ifndef IOG_MAP_PREFERENCES_H
#define IOG_MAP_PREFERENCES_H
#include <stdbool.h>
#include <stdint.h>
/* Native host preferences for a profile with the mod system deliberately off.
 * Only our fixed file inside the existing, nonlinked saves/maps directory is
 * read/written. No ROM, guest flags, SRAM or save states are touched. */
typedef struct IogMapPreferences {
    bool radar;
    uint8_t bindings[5];
} IogMapPreferences;
bool IogMapPreferencesLoad(IogMapPreferences *preferences);
bool IogMapPreferencesSave(const IogMapPreferences *preferences);
#endif
