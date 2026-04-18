import { create } from 'zustand';
import { InboxMessage } from '../types/inbox';

interface InboxState {
  messages: InboxMessage[];
  unreadCount: number;
  setMessages: (msgs: InboxMessage[]) => void;
  markRead: (id: string) => void;
  closeThread: (id: string) => void;
}

export const useInboxStore = create<InboxState>((set) => ({
  messages: [],
  unreadCount: 0,
  setMessages: (msgs) => set({ 
    messages: msgs,
    unreadCount: msgs.filter(m => m.status === 'open').length
  }),
  markRead: (id) => set((state) => {
    const messages = state.messages.map(m => m.id === id ? { ...m, status: 'read' as const } : m);
    return { messages, unreadCount: messages.filter(m => m.status === 'open').length };
  }),
  closeThread: (id) => set((state) => {
    const messages = state.messages.map(m => m.id === id ? { ...m, status: 'closed' as const } : m);
    return { messages, unreadCount: messages.filter(m => m.status === 'open').length };
  })
}));
