import { create } from 'zustand';
import { FeedItem } from '../types/message';

interface MessageState {
  feed: FeedItem[];
  addMessage: (msg: FeedItem) => void;
  clearFeed: () => void;
  isPaused: boolean;
  setPaused: (paused: boolean) => void;
}

export const useMessageStore = create<MessageState>((set) => ({
  feed: [],
  addMessage: (msg) =>
    set((state) => {
      if (state.isPaused) return state;
      const next = [msg, ...state.feed];
      if (next.length > 200) next.length = 200; // max 200 items in DOM
      return { feed: next };
    }),
  clearFeed: () => set({ feed: [] }),
  isPaused: false,
  setPaused: (paused) => set({ isPaused: paused }),
}));
