/* SPDX-License-Identifier: MIT */
#ifndef IOG_ACHIEVEMENT_AUDIT_H
#define IOG_ACHIEVEMENT_AUDIT_H

#include "progress.h"

/* Audit mode is read-only. Explicitly enabled progress uses the storage worker. */
void IogAchievementAuditStart(int argc, char **argv);
void IogAchievementAuditShutdown(void);
void IogAchievementAuditBind(void);
void IogAchievementAuditInvalidate(void);
void IogAchievementAuditFrame(unsigned frame);
const char *IogAchievementAuditSnapshot(ca_state states[CA_MAX_ACHIEVEMENTS], uint64_t *notices);
/* Developer test options, read only in a build configured with
 * IOG_ACHIEVEMENT_TEST_INPUT=ON (never packaged); NULL in every other build.
 *   IOG_ACHIEVEMENT_TEST_REFUSE_BROWSER=1  the browser fails to open, so the
 *                                          "Achievements unavailable" notice shows
 *   IOG_ACHIEVEMENT_TEST_TRACE=<dir>       log browser navigation and the chime,
 *                                          and write the browser picture after
 *                                          each change as <dir>/browser-NN.ppm */
const char *IogAchievementAuditTestOption(const char *name);

#endif
