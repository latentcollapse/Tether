import { create } from 'zustand';
import { TierId } from '../types/tier';
import { readStoredTier, writeStoredTier } from '../utils/subscription';

interface SubscriptionState {
  currentTier: TierId;
  isUpgradeModalOpen: boolean;
  openUpgradeModal: () => void;
  closeUpgradeModal: () => void;
  setCurrentTier: (tier: TierId) => void;
}

export const useSubscriptionStore = create<SubscriptionState>((set) => ({
  currentTier: readStoredTier(),
  isUpgradeModalOpen: false,
  openUpgradeModal: () => set({ isUpgradeModalOpen: true }),
  closeUpgradeModal: () => set({ isUpgradeModalOpen: false }),
  setCurrentTier: (tier) => {
    writeStoredTier(tier);
    set({ currentTier: tier });
  },
}));
