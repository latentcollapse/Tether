import { TierId } from '../types/tier';

declare global {
  interface Window {
    __TETHER_CONFIG__?: Record<string, string | undefined>;
  }
}

export type PaidTierId = 'Duo' | 'Basic' | 'Pro' | 'Enterprise';
export type CheckoutTierId = 'Duo' | 'Basic' | 'Pro';

export const SUBSCRIPTION_TIER_STORAGE_KEY = 'tether_subscription_tier';

export interface TierUsageSnapshot {
  agentsRegistered: number;
  agentsLimit: number;
  messagesUsedToday: number;
  messageLimitToday: number;
}

export interface UpgradePlan {
  id: CheckoutTierId;
  name: string;
  price: string;
  description: string;
  ctaUrl?: string;
}

const CHECKOUT_ENV_KEYS = {
  Duo: 'VITE_STRIPE_CHECKOUT_URL_DUO',
  Basic: 'VITE_STRIPE_CHECKOUT_URL_BASIC',
  Pro: 'VITE_STRIPE_CHECKOUT_URL_PRO',
} as const;

const VALID_TIERS: TierId[] = ['Free', 'Duo', 'Basic', 'Pro', 'Enterprise'];

function getConfigValue(key: 'VITE_STRIPE_CHECKOUT_URL_DUO' | 'VITE_STRIPE_CHECKOUT_URL_BASIC' | 'VITE_STRIPE_CHECKOUT_URL_PRO' | 'VITE_STRIPE_PORTAL_URL') {
  if (typeof window !== 'undefined') {
    const runtimeValue = window.__TETHER_CONFIG__?.[key];
    if (runtimeValue) {
      return runtimeValue;
    }
  }
  const envValue = import.meta.env[key];
  return typeof envValue === 'string' && envValue.length > 0 ? envValue : undefined;
}

export function normalizeTierId(value: string | null | undefined): TierId {
  return VALID_TIERS.includes(value as TierId) ? (value as TierId) : 'Free';
}

export function readStoredTier() {
  if (typeof window === 'undefined') {
    return 'Free' as TierId;
  }
  return normalizeTierId(window.localStorage.getItem(SUBSCRIPTION_TIER_STORAGE_KEY));
}

export function writeStoredTier(tier: TierId) {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(SUBSCRIPTION_TIER_STORAGE_KEY, tier);
  }
}

export function isPaidTier(tier: TierId): tier is PaidTierId {
  return tier !== 'Free';
}

export function getPortalUrl() {
  return getConfigValue('VITE_STRIPE_PORTAL_URL');
}

export function getCheckoutUrl(tier: CheckoutTierId) {
  return getConfigValue(CHECKOUT_ENV_KEYS[tier]);
}

export function openExternalUrl(url: string) {
  if (typeof window !== 'undefined') {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}

export function getTierUsageSnapshot(tier: TierId): TierUsageSnapshot {
  switch (tier) {
    case 'Duo':
      return {
        agentsRegistered: 2,
        agentsLimit: 2,
        messagesUsedToday: 180,
        messageLimitToday: 500,
      };
    case 'Basic':
      return {
        agentsRegistered: 8,
        agentsLimit: 10,
        messagesUsedToday: 8200,
        messageLimitToday: 10000,
      };
    case 'Pro':
      return {
        agentsRegistered: 38,
        agentsLimit: 100,
        messagesUsedToday: 14750,
        messageLimitToday: 50000,
      };
    case 'Enterprise':
      return {
        agentsRegistered: 112,
        agentsLimit: 500,
        messagesUsedToday: 68340,
        messageLimitToday: 250000,
      };
    case 'Free':
    case 'Indie':
    case 'Team':
    default:
      return {
        agentsRegistered: 1,
        agentsLimit: 1,
        messagesUsedToday: 96,
        messageLimitToday: 250,
      };
  }
}

export function getUpgradeTarget(tier: TierId) {
  switch (tier) {
    case 'Duo':
    case 'Free':
    case 'Indie':
    case 'Team':
      return { tier: 'Basic' as CheckoutTierId, nodes: 10 };
    case 'Basic':
      return { tier: 'Pro' as CheckoutTierId, nodes: 100 };
    case 'Pro':
      return { tier: 'Pro' as CheckoutTierId, nodes: 100 };
    case 'Enterprise':
    default:
      return null;
  }
}

export function isNearLimit(snapshot: TierUsageSnapshot) {
  const agentsRatio = snapshot.agentsRegistered / snapshot.agentsLimit;
  const messagesRatio = snapshot.messagesUsedToday / snapshot.messageLimitToday;
  return Math.max(agentsRatio, messagesRatio) >= 0.8;
}

export function getUpgradePlans(): UpgradePlan[] {
  return [
    {
      id: 'Duo',
      name: 'Duo',
      price: '$1.99/mo',
      description: 'PAKE P2P, 2 machines, direct encrypted channel',
      ctaUrl: getCheckoutUrl('Duo'),
    },
    {
      id: 'Basic',
      name: 'Basic',
      price: '$10/mo',
      description: 'Hosted relay, up to 10 nodes, WebSocket push, agent discovery',
      ctaUrl: getCheckoutUrl('Basic'),
    },
    {
      id: 'Pro',
      name: 'Pro',
      price: '$100/mo',
      description: 'Hosted relay, up to 100 nodes, same features as Basic',
      ctaUrl: getCheckoutUrl('Pro'),
    },
  ];
}
