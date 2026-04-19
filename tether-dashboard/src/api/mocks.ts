import { IssuedKey } from '../types/tier';

export const mockKeys: IssuedKey[] = [
  {
    id: 'key_1',
    agentName: 'claude@my-laptop',
    maskedKey: 'tk_live_••••••••••••abc123',
    tier: 'Free',
    issuedAt: new Date(Date.now() - 86400000 * 30).toISOString(),
    lastUsedAt: new Date(Date.now() - 120000).toISOString(),
    usage: {
      messagesUsedToday: 96,
      messageLimitToday: 250,
      agentsRegistered: 1,
      agentsLimit: 1,
      retentionDaysRemaining: 15
    },
    isActive: true
  }
];
