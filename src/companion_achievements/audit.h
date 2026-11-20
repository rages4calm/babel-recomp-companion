/* SPDX-License-Identifier: MIT */
#ifndef IOG_ACHIEVEMENT_AUDIT_H
#define IOG_ACHIEVEMENT_AUDIT_H

/* Read-only qualification of the stock achievement signals on real frames. */
void IogAchievementAuditBind(void);
void IogAchievementAuditInvalidate(void);
void IogAchievementAuditFrame(unsigned frame);

#endif
