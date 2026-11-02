/* RetroAchievements opt-out adapter. Keeps the host/game API link-compatible
 * while omitting rcheevos, HTTP, credentials and service requests entirely.
 * Upstream implementation and attribution remain in the source tree. */
#include "snes_ra.h"
#include <stdio.h>

void SnesRa_Init(const char *app_name, const char *app_version)
{ (void)app_name; (void)app_version; }
void SnesRa_Shutdown(void) {}
void SnesRa_SetEnabled(int enabled) { (void)enabled; }
int SnesRa_Enabled(void) { return 0; }
void SnesRa_LoadGameFromFile(const char *rom_path) { (void)rom_path; }
void SnesRa_SetBlocked(const char *reason) { (void)reason; }
void SnesRa_Frame(void) {}
void SnesRa_Idle(void) {}
void SnesRa_Login(const char *user, const char *password)
{ (void)user; (void)password; }
void SnesRa_Logout(void) {}
int SnesRa_LoggedIn(void) { return 0; }
void SnesRa_Status(char *out, size_t cap)
{ if (out && cap) snprintf(out, cap, "Disabled in this edition"); }
void SnesRa_GameStatus(char *out, size_t cap)
{ if (out && cap) snprintf(out, cap, "Local CompanionAchievements is independent"); }
