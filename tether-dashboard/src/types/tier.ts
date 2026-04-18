export type TierId = 'Free' | 'Indie' | 'Team' | 'Enterprise';

export interface Usage {
  messagesUsedToday: number;
  messageLimitToday: number;
  agentsRegistered: number;
  agentsLimit: number;
  retentionDaysRemaining: number;
}

export interface Tier {
  id: TierId;
  name: string;
  usage: Usage;
}

export interface IssuedKey {
  id: string;
  agentName: string;
  maskedKey: string;
  tier: TierId;
  issuedAt: string; // ISO
  lastUsedAt: string; // ISO
  usage: Usage;
  isActive: boolean;
}
