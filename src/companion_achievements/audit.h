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

#endif
