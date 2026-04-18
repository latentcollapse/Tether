import { create } from 'zustand';

interface ConnectionState {
  isConnected: boolean;
  setConnected: (status: boolean) => void;
  reconnectAttempts: number;
  incrementReconnects: () => void;
  resetReconnects: () => void;
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  isConnected: false,
  setConnected: (status) => set({ isConnected: status }),
  reconnectAttempts: 0,
  incrementReconnects: () => set((state) => ({ reconnectAttempts: state.reconnectAttempts + 1 })),
  resetReconnects: () => set({ reconnectAttempts: 0 }),
}));
