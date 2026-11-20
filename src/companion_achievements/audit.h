/* SPDX-License-Identifier: MIT */
#ifndef IOG_ACHIEVEMENT_AUDIT_H
#define IOG_ACHIEVEMENT_AUDIT_H

/* Audit mode is read-only. Explicitly enabled progress uses the storage worker. */
void IogAchievementAuditStart(int argc, char **argv);
void IogAchievementAuditShutdown(void);
void IogAchievementAuditBind(void);
void IogAchievementAuditInvalidate(void);
void IogAchievementAuditFrame(unsigned frame);

#endif
